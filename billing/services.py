"""Billing App — Service Layer"""
import logging
from django.db import transaction
from django.utils import timezone
from .models import Invoice, InvoiceItem, Payment, PaymentStatus

logger = logging.getLogger('billing')


class BillingService:

    @staticmethod
    @transaction.atomic
    def create_invoice(patient, created_by, appointment=None,
                       items_data=None, tax_amount=0, discount=0, notes=''):
        invoice = Invoice.objects.create(
            patient=patient,
            created_by=created_by,
            appointment=appointment,
            tax_amount=tax_amount,
            discount=discount,
            notes=notes,
        )
        if items_data:
            for item in items_data:
                InvoiceItem.objects.create(invoice=invoice, **item)
        invoice.recalculate_totals()
        logger.info('Invoice created: %s for %s', invoice.invoice_number, patient.full_name)
        return invoice

    @staticmethod
    @transaction.atomic
    def record_payment(invoice, amount, payment_method, gateway_txn_id='', payment_channel='COUNTER', razorpay_order_id=''):
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_channel=payment_channel,
            payment_method=payment_method,
            gateway_txn_id=gateway_txn_id,
            razorpay_order_id=razorpay_order_id,
            status=PaymentStatus.COMPLETED,
            paid_at=timezone.now(),
        )
        total_paid = sum(p.amount for p in invoice.payments.filter(status=PaymentStatus.COMPLETED))
        if total_paid >= invoice.total_amount:
            invoice.payment_status = PaymentStatus.COMPLETED
        elif total_paid > 0:
            invoice.payment_status = PaymentStatus.PARTIAL
        invoice.save(update_fields=['payment_status', 'updated_at'])

        if invoice.appointment and invoice.payment_status == PaymentStatus.COMPLETED:
            from appointments.models import AppointmentStatus
            appt = invoice.appointment
            if appt.status in ['DISPENSED', 'CONSULTATION_DONE']:
                appt.status = AppointmentStatus.COMPLETED
                appt.save(update_fields=['status', 'updated_at'])

        logger.info('Payment recorded: ₹%s for %s', amount, invoice.invoice_number)
        return payment

    @staticmethod
    def create_razorpay_order(invoice):
        """
        Creates an online payment order in Razorpay.
        Supports Mock mode for offline local testing.
        """
        from django.conf import settings
        import razorpay

        amount_in_paise = int(invoice.total_amount * 100)  # Razorpay accepts amounts in Paise

        if settings.RAZORPAY_MOCK:
            logger.info("Razorpay Mock Order created for Invoice %s", invoice.invoice_number)
            return {
                "id": f"order_mock_{invoice.id.hex[:14]}",
                "entity": "order",
                "amount": amount_in_paise,
                "amount_paid": 0,
                "amount_due": amount_in_paise,
                "currency": "INR",
                "receipt": invoice.invoice_number,
                "status": "created",
                "created_at": int(timezone.now().timestamp())
            }

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order_data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": invoice.invoice_number,
            "payment_capture": 1  # Auto capture payment
        }
        try:
            order = client.order.create(data=order_data)
            logger.info("Razorpay Order created: %s", order['id'])
            return order
        except Exception as e:
            logger.error("Failed to create Razorpay order: %s", str(e))
            raise ValueError(f"Razorpay error: {str(e)}")

    @staticmethod
    @transaction.atomic
    def verify_razorpay_payment(invoice, razorpay_payment_id, razorpay_order_id, razorpay_signature):
        """
        Verifies the signature returned by Razorpay Checkout.
        Saves transaction and updates Invoice Status on success.
        """
        from django.conf import settings
        import razorpay

        if settings.RAZORPAY_MOCK:
            logger.info("Mock Verification Successful for Invoice %s", invoice.invoice_number)
            # Record payment directly
            BillingService.record_payment(
                invoice=invoice,
                amount=invoice.total_amount,
                payment_method='UPI',
                gateway_txn_id=razorpay_payment_id,
                payment_channel='ONLINE',
                razorpay_order_id=razorpay_order_id
            )
            return True

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        try:
            client.utility.verify_payment_signature(params_dict)
            logger.info("Razorpay Signature Verified for Order %s", razorpay_order_id)
            
            # Record payment transaction
            BillingService.record_payment(
                invoice=invoice,
                amount=invoice.total_amount,
                payment_method='UPI',  # We assume UPI/Card, updated by webhook if needed
                gateway_txn_id=razorpay_payment_id,
                payment_channel='ONLINE',
                razorpay_order_id=razorpay_order_id
            )
            return True
        except Exception as e:
            logger.error("Signature Verification Failed: %s", str(e))
            return False

    @staticmethod
    def handle_razorpay_webhook(payload, signature):
        """
        Processes callbacks directly from Razorpay's server.
        Useful for when users complete payment but close the app before client-side verification completes.
        """
        from django.conf import settings
        import razorpay
        import json

        if settings.RAZORPAY_MOCK:
            logger.warning("Mock webhook ignored. Webhooks require live/sandbox server endpoints.")
            return False

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            client.utility.verify_webhook_signature(
                body=json.dumps(payload),
                signature=signature,
                secret=settings.RAZORPAY_KEY_SECRET
            )
        except Exception as e:
            logger.error("Webhook signature verification failed: %s", str(e))
            return False

        # Process standard webhook payloads
        event = payload.get("event")
        if event == "payment.captured":
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            amount = payment_entity.get("amount", 0) / 100.0  # Convert back from Paise
            method_type = payment_entity.get("method", "UPI").upper()

            # Map method types to our PaymentMethod choices
            method_mapping = {
                "CARD": "CREDIT_CARD",
                "NETBANKING": "NET_BANKING",
                "WALLET": "WALLET",
                "UPI": "UPI"
            }
            mapped_method = method_mapping.get(method_type, "UPI")

            try:
                # Find matching payment record by order_id
                payment = Payment.objects.get(razorpay_order_id=order_id)
                invoice = payment.invoice
                
                # Check if it was already marked as completed to avoid double counting
                if invoice.payment_status != PaymentStatus.COMPLETED:
                    with transaction.atomic():
                        payment.status = PaymentStatus.COMPLETED
                        payment.gateway_txn_id = payment_id
                        payment.payment_method = mapped_method
                        payment.paid_at = timezone.now()
                        payment.save()

                        # Recompute invoice status
                        total_paid = sum(p.amount for p in invoice.payments.filter(status=PaymentStatus.COMPLETED))
                        if total_paid >= invoice.total_amount:
                            invoice.payment_status = PaymentStatus.COMPLETED
                            invoice.save(update_fields=["payment_status", "updated_at"])
                            
                            # Complete appointment status
                            if invoice.appointment:
                                from appointments.models import AppointmentStatus
                                appt = invoice.appointment
                                if appt.status in ['DISPENSED', 'CONSULTATION_DONE']:
                                    appt.status = AppointmentStatus.COMPLETED
                                    appt.save(update_fields=['status', 'updated_at'])
                        
                    logger.info("Webhook: Order %s updated successfully via payment %s", order_id, payment_id)
                    return True
            except Payment.DoesNotExist:
                logger.error("Webhook Error: No payment record found matching Order ID %s", order_id)
                
        return False

