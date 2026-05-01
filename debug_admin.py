import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medconnect.settings')
import django
django.setup()

from accounts.models import User

# Check admin user
admin = User.objects.filter(role='ADMIN').first()

if admin:
    print(f"Username:        {admin.username}")
    print(f"Has password:    {admin.has_usable_password()}")
    print(f"Password works:  {admin.check_password('admin@123')}")
    print(f"Is active:       {admin.is_active}")
    print(f"USERNAME_FIELD:  {User.USERNAME_FIELD}")
    print(f"Auth backends:   see settings")
else:
    print("NO ADMIN USER EXISTS")
