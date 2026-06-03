import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medconnect.settings')
django.setup()

from accounts.models import User

users = User.objects.all().order_by('user_id')

print('\n' + '='*150)
print(f"{'USER_ID':<30} {'USERNAME':<25} {'FULL_NAME':<30} {'ROLE':<15} {'PHONE':<18} {'EMAIL':<30}")
print('='*150)

for u in users:
    email = u.email if u.email else 'N/A'
    print(f"{u.user_id:<30} {u.username:<25} {u.full_name:<30} {u.role:<15} {u.phone:<18} {email:<30}")

print('='*150)
print(f'\nTotal Users: {users.count()}\n')
