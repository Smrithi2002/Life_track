# MedConnect Architecture

MedConnect follows a modular "Clinic First → Hospital Scalable" architecture. This allows the system to be deployed as a lightweight setup for small clinics, while remaining fully scalable for multi-department hospitals.

## Multi-Tenancy & Single-Tenancy

The system is designed with a **Multi-Tenant Foundation**.
Every core entity (User, Department, DoctorProfile, Appointment, Medicine, Prescription, Invoice) is linked to an `Organization`.

Currently, the system operates in a **Single-Tenant** mode:
1. `OrganizationMiddleware` automatically attaches the active `Organization` to `request.organization`.
2. All new records are automatically scoped to this organization if applicable.
3. To scale to a SaaS/Multi-Tenant model in the future, we simply update the middleware to resolve the organization via domain/subdomain or JWT claims.

## Setup Modes

The system operates in one of two modes, determined by the `setup_type` field on the `Organization` model:

1. **CLINIC Mode**
   - Lightweight configuration.
   - Departments are disabled (Doctors operate independently).
   - In-Patient Department (IPD) is disabled.
   - Complex lab workflows are disabled.
   - Ideal for solo practitioners or small polyclinics.

2. **HOSPITAL Mode**
   - Full enterprise configuration.
   - Departments are mandatory for doctor routing.
   - IPD, Lab, Pharmacy, and Analytics are enabled.

## Feature Toggling System

Instead of hardcoding "if CLINIC do X, else do Y", we use a **Feature Toggle System**. The `Organization` model contains boolean flags for each module (e.g., `enable_departments`, `enable_lab`).

### How to gate a feature:

**In DRF Views using Permission Classes:**
```python
from organizations.features import DepartmentsFeatureRequired

class DepartmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DepartmentsFeatureRequired()]
```

**In Python Logic using FeatureToggle:**
```python
from organizations.features import FeatureToggle

if FeatureToggle.is_enabled(request.organization, 'enable_lab'):
    # execute lab specific logic
```

## Future Expansion

To add a new module (e.g., Blood Bank):
1. Create the Django app (`python manage.py startapp bloodbank`).
2. Add a new boolean flag to `Organization` (`enable_blood_bank`).
3. Add it to `KNOWN_FEATURES` in `organizations/features.py`.
4. Gate the `bloodbank` endpoints using `FeatureRequired('enable_blood_bank')`.
