# Feature Toggles Guide

The MedConnect architecture relies on feature toggles to adapt the application between different environments (e.g. Clinic vs. Hospital). This document describes how feature toggles work, how to use them, and how to define new ones.

## 1. Defining Feature Toggles

Feature toggles are defined on the `Organization` model (`organizations.models.Organization`) as boolean fields. 

If you are adding a new feature module, add a boolean field to the model:

```python
enable_new_feature = models.BooleanField(default=False)
```

Then, register it in `organizations/features.py` under `KNOWN_FEATURES`:

```python
KNOWN_FEATURES = {
    'enable_departments',
    'enable_lab',
    'enable_pharmacy',
    # ...
    'enable_new_feature',
}
```

## 2. Using Feature Toggles in Code

### In Django/DRF Views (Permission Classes)

The preferred way to restrict access to an entire viewset or view is by using the `FeatureRequired` factory:

```python
from organizations.features import FeatureRequired

class MyFeatureViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, FeatureRequired('enable_new_feature')]
    # ...
```

This will automatically check if `request.organization.enable_new_feature` is True. If False, it returns a `403 Forbidden` with a standardized error payload indicating the module is disabled.

There are pre-built permissions for convenience:
```python
from organizations.features import DepartmentsFeatureRequired, LabFeatureRequired
```

### In Python Logic (Inline)

If you need to conditionally execute logic inside a method or serializer:

```python
from organizations.features import FeatureToggle

def process_order(request):
    if FeatureToggle.is_enabled(request.organization, 'enable_new_feature'):
        # Do something
        pass
```

### As a Function Decorator

If you are using function-based views or want to decorate specific class methods:

```python
from organizations.features import require_feature

@require_feature('enable_new_feature')
def custom_endpoint(request):
    pass
```

## 3. Fallback to Settings

When an `Organization` record is not yet created or not attached to the request, `FeatureToggle.is_enabled()` will fall back to `settings.ORGANIZATION_DEFAULTS`.

```python
# settings/base.py
ORGANIZATION_DEFAULTS = {
    'setup_type': 'CLINIC',
    'enable_departments': False,
    'enable_new_feature': True,
}
```

This ensures the system degrades gracefully into a single-tenant default state.
