"""
Management Command: create_default_organization
================================================
Creates the default Organization record for single-tenant deployments.
Run this ONCE after the initial migration.

Usage:
    python manage.py create_default_organization
    python manage.py create_default_organization --name "My Clinic" --type CLINIC
    python manage.py create_default_organization --name "City Hospital" --type HOSPITAL
    python manage.py create_default_organization --backfill  # Link existing records to org

Options:
    --name      Organization name (default: "MedConnect Clinic")
    --type      CLINIC or HOSPITAL (default: CLINIC)
    --slug      URL slug (auto-generated from name if not given)
    --city      City name
    --phone     Contact phone
    --backfill  Auto-link all existing users/patients/appointments to this org
    --force     Recreate even if an organization already exists
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from organizations.models import Organization, SetupType


class Command(BaseCommand):
    help = 'Create the default organization for single-tenant clinic/hospital setup.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            default='MedConnect Clinic',
            help='Organization name (default: "MedConnect Clinic")',
        )
        parser.add_argument(
            '--type',
            default='CLINIC',
            choices=['CLINIC', 'HOSPITAL'],
            dest='setup_type',
            help='Setup type: CLINIC or HOSPITAL (default: CLINIC)',
        )
        parser.add_argument(
            '--slug',
            default=None,
            help='URL slug (auto-generated from name if not provided)',
        )
        parser.add_argument(
            '--city',
            default='',
            help='City name for the organization',
        )
        parser.add_argument(
            '--phone',
            default='',
            help='Contact phone number',
        )
        parser.add_argument(
            '--backfill',
            action='store_true',
            default=False,
            help='Backfill: assign existing records (users, appointments, etc.) to this org',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Force recreation even if an organization already exists',
        )

    def handle(self, *args, **options):
        name       = options['name']
        setup_type = options['setup_type']
        slug       = options['slug'] or slugify(name)
        city       = options['city']
        phone      = options['phone']
        backfill   = options['backfill']
        force      = options['force']

        # ── Check if org already exists ───────────────────────────────
        existing = Organization.objects.first()
        if existing and not force:
            self.stdout.write(self.style.WARNING(
                '\n[WARNING] Organization already exists: "{}" '
                '(setup_type={})\n'
                '   Use --force to recreate or update it.\n'
                '   Run with --backfill to assign existing records to this org.\n'.format(
                    existing.name, existing.setup_type
                )
            ))
            if backfill:
                self._backfill(existing)
            return

        # ── Create organization ───────────────────────────────────────
        # Ensure slug uniqueness
        base_slug = slug
        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1

        org = Organization(
            name=name,
            slug=slug,
            setup_type=setup_type,
            city=city,
        )

        if phone:
            org.phone = phone

        # Auto-apply defaults (handled in Organization.save())
        org.save()

        self.stdout.write(self.style.SUCCESS(
            '\n[OK] Organization created successfully!\n'
            '   Name:       {}\n'
            '   Slug:       {}\n'
            '   Setup Type: {}\n'
            '   ID:         {}\n'
            '\n   Feature Flags:\n'.format(org.name, org.slug, org.setup_type, org.id)
        ))

        for feat, val in org.get_feature_map().items():
            icon = '[ON] ' if val else '[OFF]'
            self.stdout.write(f'   {icon} {feat}: {val}')

        # ── Backfill existing records ─────────────────────────────────
        if backfill:
            self._backfill(org)

        self.stdout.write(self.style.SUCCESS(
            '\n   [DONE] Setup complete! You can now start the server.\n'
        ))

    def _backfill(self, org):
        """
        Assign all existing records (with organization=NULL) to this org.
        This is safe to run multiple times -- only updates NULL records.
        """
        self.stdout.write('\n   [INFO] Starting backfill of existing records...\n')

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            updated = User.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] Users backfilled:        {updated}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   [SKIP] Users backfill skipped: {e}'))

        try:
            from appointments.models import Department, DoctorProfile, Appointment
            n = Department.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] Departments backfilled:  {n}'))
            n = DoctorProfile.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] DoctorProfiles backfilled:{n}'))
            n = Appointment.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] Appointments backfilled: {n}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   [SKIP] Appointments backfill skipped: {e}'))

        try:
            from prescriptions.models import Medicine, Prescription
            n = Medicine.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] Medicines backfilled:    {n}'))
            n = Prescription.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] Prescriptions backfilled:{n}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   [SKIP] Prescriptions backfill skipped: {e}'))

        try:
            from billing.models import Invoice
            n = Invoice.objects.filter(organization__isnull=True).update(organization=org)
            self.stdout.write(self.style.SUCCESS(f'   [OK] Invoices backfilled:     {n}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   [SKIP] Billing backfill skipped: {e}'))

        self.stdout.write(self.style.SUCCESS('   [DONE] Backfill complete!\n'))
