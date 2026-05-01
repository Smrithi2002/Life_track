"""
MedConnect — Setup Script
===========================
Creates initial admin user and test users for development.
Run: python setup_admin.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medconnect.settings')
django.setup()

from accounts.models import User, UserRole

def create_admin():
    """Create the initial admin superuser."""
    if User.objects.filter(role=UserRole.ADMIN).exists():
        admin = User.objects.filter(role=UserRole.ADMIN).first()
        print(f'\n✅ Admin already exists:')
        print(f'   User ID  : {admin.user_id}')
        print(f'   Username : {admin.username}')
        print(f'   Phone    : {admin.phone}')
        return admin

    admin = User.objects.create_superuser(
        phone='+919999999999',
        password='admin@123',
        username='admin',
        full_name='Super Admin',
    )
    print(f'\n✅ Admin created successfully!')
    print(f'   User ID  : {admin.user_id}')
    print(f'   Username : {admin.username}')
    print(f'   Password : admin@123')
    print(f'   Phone    : {admin.phone}')
    return admin


def create_test_users():
    """Create test users for each role."""
    test_users = [
        {
            'phone': '+919876543001',
            'full_name': 'Dr. Arun Kumar',
            'role': UserRole.DOCTOR,
            'password': 'doctor@123',
            'gender': 'MALE',
        },
        {
            'phone': '+919876543002',
            'full_name': 'Nurse Priya Nair',
            'role': UserRole.NURSE,
            'password': 'nurse@123',
            'gender': 'FEMALE',
        },
        {
            'phone': '+919876543003',
            'full_name': 'Pharmacist Rahul Menon',
            'role': UserRole.PHARMACIST,
            'password': 'pharma@123',
            'gender': 'MALE',
        },
        {
            'phone': '+919876543004',
            'full_name': 'Reception Anitha S',
            'role': UserRole.RECEPTION,
            'password': 'reception@123',
            'gender': 'FEMALE',
        },
        {
            'phone': '+919876543005',
            'full_name': 'Patient Mohan Das',
            'role': UserRole.PATIENT,
            'password': 'patient@123',
            'gender': 'MALE',
        },
    ]

    print(f'\n📋 Creating test users...\n')
    print(f'{"Role":<15} {"User ID":<25} {"Name":<25} {"Password":<15}')
    print(f'{"─" * 80}')

    for data in test_users:
        phone = data['phone']
        if User.objects.filter(phone=phone).exists():
            user = User.objects.get(phone=phone)
            print(f'{user.get_role_display():<15} {user.user_id:<25} {user.full_name:<25} (already exists)')
            continue

        if data['role'] in [UserRole.DOCTOR, UserRole.NURSE, UserRole.PHARMACIST, UserRole.RECEPTION]:
            user = User.objects.create_staffuser(
                phone=data['phone'],
                password=data['password'],
                role=data['role'],
                full_name=data['full_name'],
                gender=data.get('gender', ''),
            )
        else:
            user = User.objects.create_user(
                phone=data['phone'],
                password=data['password'],
                role=data['role'],
                full_name=data['full_name'],
                gender=data.get('gender', ''),
            )

        print(f'{user.get_role_display():<15} {user.user_id:<25} {user.full_name:<25} {data["password"]:<15}')

    print(f'\n✅ All test users created!')


if __name__ == '__main__':
    print('=' * 60)
    print('  MedConnect — Initial Setup')
    print('=' * 60)

    create_admin()
    create_test_users()

    print(f'\n{"=" * 60}')
    print(f'  LOGIN: Use the User ID + Password shown above')
    print(f'  Example: POST /api/v1/auth/login')
    print(f'  Body: {{ "user_id": "MC-ADM-2026-00001", "password": "admin@123" }}')
    print(f'{"=" * 60}\n')
