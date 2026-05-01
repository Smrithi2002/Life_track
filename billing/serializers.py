"""Billing App — Serializers"""
from rest_framework import serializers
from .models import Invoice, InvoiceItem, Payment


class InvoiceItemSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_item_type_display', read_only=True)

    class Meta:
        model = InvoiceItem
        fields = ['id', 'item_type', 'type_display', 'description', 'quantity', 'unit_price', 'total']
        read_only_fields = ['id', 'total']


class PaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'amount', 'payment_method', 'method_display',
            'gateway_txn_id', 'status', 'status_display',
            'receipt_url', 'paid_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class InvoiceSerializer(serializers.ModelSerializer):
    patient_name    = serializers.CharField(source='patient.full_name', read_only=True)
    patient_user_id = serializers.CharField(source='patient.user_id', read_only=True)
    status_display  = serializers.CharField(source='get_payment_status_display', read_only=True)
    items           = InvoiceItemSerializer(many=True, read_only=True)
    payments        = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'appointment',
            'patient', 'patient_name', 'patient_user_id',
            'created_by', 'subtotal', 'tax_amount', 'discount', 'total_amount',
            'payment_status', 'status_display', 'notes', 'due_date',
            'items', 'payments', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at']


class InvoiceCreateSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, write_only=True)

    class Meta:
        model = Invoice
        fields = ['appointment', 'patient', 'tax_amount', 'discount', 'notes', 'due_date', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        invoice = Invoice.objects.create(
            created_by=self.context['request'].user,
            **validated_data,
        )
        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)
        invoice.recalculate_totals()
        return invoice


class PaymentCreateSerializer(serializers.Serializer):
    invoice = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=Payment._meta.get_field('payment_method').choices)
    gateway_txn_id = serializers.CharField(required=False, allow_blank=True, default='')
