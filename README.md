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
**User side tabs**
1. **Basic Info** — name, age, place, blood group, allergies, relation.
2. **Add Report** — upload a PDF, tag it, set the report/diagnosis date.
3. **View Reports** — searchable (by tag / filename / date) list of uploaded reports.
4. **Prescriptions** — view prescription images (added by doctor or self);
5. **Medicine Reminders** — medicine name, dosage, timing (before/after meals,
   bedtime — multi-select), and duration (fixed number of days or "every day").
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

## Points to be noted before scaling up

- **Google Drive**: file storage currently uses a local `storage/<app_id>/...`
  folder (see `storage.py`). It's deliberately isolated into a few small
  functions (`save_file`, `get_file_path`, `delete_file`) so that swapping
  in the real Google Drive API later only means rewriting `storage.py` —
  nothing else in the app needs to change.
- **Passwords** are hashed with `bcrypt` — never stored in plain text.
- **OTP delivery**: since there's no real SMS gateway wired in yet, OTPs are
  shown directly in the patient's own dashboard as an in-app alert. 
- **Reminders** are pull-based (shown when the user opens the app / tab),
  not push notifications.
- **Phone number validation** currently assumes Indian 10-digit mobile
  numbers (starting with 6–9). Easy to change if needed.
- This is a **single-process SQLite app** — fine for a prototype/demo, but
  not meant for concurrent multi-user production load.

## Some future thinking

- Real SMS/OTP gateway for doctor-side login or patient OTP delivery.
- Real cloud storage integration. 
- Doctor's own "my patients" list and appointment calender.
- Editing/deleting reports & prescriptions, not just adding.
- Per-family-member PIN if they want privacy between family members sharing
  one phone login.
