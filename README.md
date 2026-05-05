# MedConnect — Digital Healthcare Platform (Backend)

MedConnect is a comprehensive, production-ready healthcare management system built with a modular Django architecture. It supports multi-role access (Admin, Doctor, Nurse, Pharmacist, Reception, Patient) and handles the entire clinical workflow.

## 🏗 Modular Architecture
The project is divided into six core modules following the **Router → Serializer → Service → Permission** pattern:

- **`accounts`**: Custom user management, RBAC, and OTP-based authentication.
- **`appointments`**: Department management, doctor scheduling, and appointment lifecycle.
- **`healthcard`**: NFC/QR-enabled patient health cards with audit logs.
- **`prescriptions`**: Medicine catalog and pharmacy dispensing workflow.
- **`medical_records`**: Clinical documentation, ICD-10 diagnoses, and lab reports.
- **`billing`**: Invoice generation and payment gateway integration.

## 🚀 Key Features
- **Appointment Lifecycle:** `BOOKED` → `CHECKED_IN` → `VITALS_DONE` → `WITH_DOCTOR` → `COMPLETED`.
- **Queue Management:** Token-based system for patient flow.
- **Role-Based Access Control (RBAC):** Strict permissions for medical data privacy.
- **Service Layer:** All business logic is decoupled from views for better testability.
- **Audit Trails:** Tracking health card scans and data modifications.

## 🛠 Tech Stack
- **Framework:** Django 5.x + Django REST Framework
- **Database:** PostgreSQL (Production) / SQLite (Dev)
- **Auth:** JWT (SimpleJWT) + Custom OTP Backend
- **Documentation:** Swagger/OpenAPI

## 📖 Getting Started
1. Clone the repo: `git clone https://github.com/Smrithi2002/Life_track.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run migrations: `python manage.py migrate`
4. Start dev server: `python manage.py runserver`

## 👨‍💻 Git Workflow
We follow the **Git Flow** strategy:
- `main`: Stable production code.
- `develop`: Development integration branch.
- `feature/*`: New feature development.
- `hotfix/*`: Emergency fixes.
