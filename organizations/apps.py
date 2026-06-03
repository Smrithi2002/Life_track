from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organizations'
    verbose_name = 'Organizations'

    def ready(self):
        """Import signals when app is ready."""
        pass  # signals can be imported here in future
