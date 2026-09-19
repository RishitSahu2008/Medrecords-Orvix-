# MedRecords — Prototype

A pure-Python (Streamlit) prototype for a centralized medical records +
appointment/reminder app, with a **user (patient/family) side** and a
**doctor side**.

## How to run

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

The first run auto-creates `medapp.db` (SQLite) and a `storage/` folder
(placeholder for Google Drive — see note below).

## Project structure

```
medapp/
├── app.py            # Main entry point: landing / register / login / routing
├── database.py        # SQLite schema + all CRUD functions
├── auth.py             # Password hashing, login/registration logic
├── storage.py          # File storage (local folder now, swap for Drive later)
├── reminders.py        # Logic for "is this medicine/follow-up due today"
├── user_side.py        # All 6 patient-side tabs
├── doctor_side.py      # Doctor home + OTP-gated patient record access
├── requirements.txt
└── storage/             # Uploaded reports & prescriptions land here
```

## How each of your requirements was implemented

**Login**
- Doctor: phone number + password only (no OTP), phone number is unique per doctor.
- User: phone number + password only. Up to **4 family members** can share
  one phone number/login; each family member gets a unique **App ID**
  (e.g. `U552783`). After login, the user picks which family member's
  profile to use.

**Registration**
- Separate registration page, with two tabs: **Doctor Registration** and
  **User / Family Registration**. A new user account first creates the
  phone+password login, then family members are added (up to 4) from the
  "Who's using the app?" screen after logging in.

**User side tabs** (per family member / App ID):
1. **Basic Info** — name, age, place, blood group, allergies, relation.
2. **Add Report** — upload a PDF, tag it, set the report/diagnosis date.
3. **View Reports** — searchable (by tag / filename / date) list of uploaded reports.
4. **Prescriptions** — view prescription images (added by doctor or self);
   small "+ Add a prescription" panel at the top; tagging + search included.
5. **Medicine Reminders** — medicine name, dosage, timing (before/after meals,
   bedtime — multi-select), and duration (fixed number of days or "every day").
   The "Active Reminders (today)" section shows what's due right now.
6. **Follow-Up Alerts** — read-only view of follow-ups set by doctors,
   shown as alerts (upcoming / today / missed).

**Doctor side**
- Home page: doctor's name, hospital/clinic, speciality, location.
- **Patient access flow**: doctor enters the patient's App ID → system
  generates a one-time OTP → the OTP is **not sent via SMS** (this is a
  prototype) — instead it appears as an alert banner on the patient's own
  dashboard when they're logged in, which they read out to the doctor.
  Doctor enters that OTP → records unlock.
- OTP is a **single-use token that also expires after 5 minutes**: it's
  deleted from the database the moment it's verified successfully (so it
  can never be reused), and it's also automatically invalidated/cleaned up
  if 5 minutes pass without being used. If a doctor enters a correct-but-
  expired code, they're told to request a new one.
- Once access is granted, the doctor can view basic info, reports, and
  prescriptions, **add a new prescription**, and **set a follow-up date/time**
  (which then shows up as an alert on the patient's side).

## Design notes / things to know before you scale this up

- **Google Drive**: file storage currently uses a local `storage/<app_id>/...`
  folder (see `storage.py`). It's deliberately isolated into a few small
  functions (`save_file`, `get_file_path`, `delete_file`) so that swapping
  in the real Google Drive API later only means rewriting `storage.py` —
  nothing else in the app needs to change. Send over the Drive folder/
  credentials whenever you're ready and I'll wire it in.
- **Passwords** are hashed with `bcrypt` — never stored in plain text.
- **OTP delivery**: since there's no real SMS gateway wired in yet, OTPs are
  shown directly in the patient's own dashboard as an in-app alert. This
  keeps the "OTP-based consent" concept intact for the prototype without
  needing a paid SMS service.
- **Reminders** are pull-based (shown when the user opens the app / tab),
  not push notifications — as agreed, no background notification service
  is running in this version.
- **Phone number validation** currently assumes Indian 10-digit mobile
  numbers (starting with 6–9). Easy to change in `auth.py` if needed.
- This is a **single-process SQLite app** — fine for a prototype/demo, but
  not meant for concurrent multi-user production load. For that you'd
  move to PostgreSQL/MySQL later.

## Suggested next steps (not built yet, just flagging)

- Real SMS/OTP gateway for doctor-side login or patient OTP delivery.
- Real Google Drive (or S3/cloud storage) integration.
- Doctor's own "my patients" list / appointment calendar view.
- Editing/deleting reports & prescriptions, not just adding.
- Per-family-member PIN if you want privacy between family members sharing
  one phone login.
