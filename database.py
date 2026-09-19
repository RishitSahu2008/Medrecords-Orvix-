"""
database.py
Handles SQLite connection, schema creation, and all CRUD helper
functions used across the app (accounts, doctors, family members,
reports, prescriptions, reminders, follow-ups, OTPs).
"""

import sqlite3
import os
import random
import string
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medapp.db")

OTP_EXPIRY_MINUTES = 5


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Accounts = the login credential (phone + password) shared by a family (max 4 members)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Family members = individual patients, each with a unique app_id, linked to an account
    cur.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            app_id TEXT PRIMARY KEY,
            account_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date_of_birth TEXT,
            gender TEXT,
            place TEXT,
            blood_group TEXT,
            allergies TEXT,
            relation TEXT,
            email TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        )
    """)

    # Doctors = separate login, unique phone number, no OTP needed to log in
    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id TEXT PRIMARY KEY,
            phone_number TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            hospital TEXT,
            speciality TEXT,
            location TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Reports (blood test, x-ray, etc.) uploaded by the patient
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            report_date TEXT NOT NULL,
            tags TEXT,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (app_id) REFERENCES family_members(app_id)
        )
    """)

    # Prescriptions (images) - added by doctor (after OTP access) or by user themselves
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            prescription_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            tags TEXT,
            added_by TEXT NOT NULL,       -- 'doctor' or 'user'
            added_by_id TEXT,             -- doctor_id if added by doctor
            added_at TEXT NOT NULL,
            FOREIGN KEY (app_id) REFERENCES family_members(app_id)
        )
    """)

    # Medicine reminders set by the user
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medicine_reminders (
            reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT NOT NULL,
            medicine_name TEXT NOT NULL,
            dosage TEXT,
            timing TEXT,                  -- e.g. "After Lunch, After Dinner"
            start_date TEXT NOT NULL,
            duration_days INTEGER,        -- NULL/0 means "everyday / ongoing"
            everyday INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (app_id) REFERENCES family_members(app_id)
        )
    """)

    # Follow-up reminders set by the doctor, viewed as alerts by the user
    cur.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            followup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT NOT NULL,
            doctor_id TEXT NOT NULL,
            followup_date TEXT NOT NULL,
            followup_time TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (app_id) REFERENCES family_members(app_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
        )
    """)

    # OTPs generated when a doctor requests access to a patient's record.
    # No expiry - deleted immediately once used successfully (one-time use).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_otps (
            otp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT NOT NULL,
            doctor_id TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (app_id) REFERENCES family_members(app_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
        )
    """)

    conn.commit()
    _run_migrations(conn)
    conn.close()


def _run_migrations(conn):
    """
    Safely add new columns to existing databases without wiping data.
    Each check is skipped if the column already exists (e.g. on a brand
    new database where CREATE TABLE already included it).
    """
    cur = conn.cursor()

    # --- family_members migrations ---
    fm_columns = [row["name"] for row in cur.execute("PRAGMA table_info(family_members)")]

    if "gender" not in fm_columns:
        cur.execute("ALTER TABLE family_members ADD COLUMN gender TEXT")
        conn.commit()

    if "email" not in fm_columns:
        cur.execute("ALTER TABLE family_members ADD COLUMN email TEXT")
        conn.commit()

    if "date_of_birth" not in fm_columns:
        cur.execute("ALTER TABLE family_members ADD COLUMN date_of_birth TEXT")
        conn.commit()
        # If the old 'age' column exists, estimate a date_of_birth from it
        # (Jan 1st of the appropriate year) so existing records keep working
        # until the user corrects it with their real DOB.
        if "age" in fm_columns:
            rows = cur.execute("SELECT app_id, age FROM family_members").fetchall()
            for row in rows:
                if row["age"] is not None:
                    estimated_year = date.today().year - int(row["age"])
                    estimated_dob = f"{estimated_year}-01-01"
                    cur.execute(
                        "UPDATE family_members SET date_of_birth = ? WHERE app_id = ?",
                        (estimated_dob, row["app_id"])
                    )
            conn.commit()

    # --- doctors migrations ---
    doc_columns = [row["name"] for row in cur.execute("PRAGMA table_info(doctors)")]
    if "email" not in doc_columns:
        cur.execute("ALTER TABLE doctors ADD COLUMN email TEXT")
        conn.commit()


# ---------------------------------------------------------------------------
# Age calculation
# ---------------------------------------------------------------------------

def calculate_age(date_of_birth_str):
    """Compute current age (in whole years) from a 'YYYY-MM-DD' date of birth string."""
    if not date_of_birth_str:
        return None
    try:
        dob = datetime.strptime(date_of_birth_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


# ---------------------------------------------------------------------------
# ID generation helpers
# ---------------------------------------------------------------------------

def _random_digits(n):
    return "".join(random.choices(string.digits, k=n))


def generate_unique_app_id():
    conn = get_connection()
    cur = conn.cursor()
    while True:
        candidate = "U" + _random_digits(6)
        cur.execute("SELECT 1 FROM family_members WHERE app_id = ?", (candidate,))
        if cur.fetchone() is None:
            conn.close()
            return candidate


def generate_unique_doctor_id():
    conn = get_connection()
    cur = conn.cursor()
    while True:
        candidate = "D" + _random_digits(6)
        cur.execute("SELECT 1 FROM doctors WHERE doctor_id = ?", (candidate,))
        if cur.fetchone() is None:
            conn.close()
            return candidate


def generate_otp_code():
    return _random_digits(6)


# ---------------------------------------------------------------------------
# Account (phone + password) helpers
# ---------------------------------------------------------------------------

def get_account_by_phone(phone_number):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM accounts WHERE phone_number = ?", (phone_number,)
    ).fetchone()
    conn.close()
    return row


def create_account(phone_number, password_hash):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accounts (phone_number, password_hash, created_at) VALUES (?, ?, ?)",
        (phone_number, password_hash, datetime.now().isoformat()),
    )
    conn.commit()
    account_id = cur.lastrowid
    conn.close()
    return account_id


def count_family_members(account_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM family_members WHERE account_id = ?", (account_id,)
    ).fetchone()
    conn.close()
    return row["c"]


def add_family_member(account_id, name, date_of_birth, gender, place, blood_group, allergies, relation, email=None):
    app_id = generate_unique_app_id()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO family_members
        (app_id, account_id, name, date_of_birth, gender, place, blood_group, allergies, relation, email, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (app_id, account_id, name, date_of_birth, gender, place, blood_group, allergies, relation, email,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return app_id


def get_family_members(account_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM family_members WHERE account_id = ? ORDER BY created_at",
        (account_id,)
    ).fetchall()
    conn.close()
    return rows


def get_family_member(app_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM family_members WHERE app_id = ?", (app_id,)
    ).fetchone()
    conn.close()
    return row


def update_basic_info(app_id, name, date_of_birth, gender, place, blood_group, allergies, relation, email=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE family_members
        SET name = ?, date_of_birth = ?, gender = ?, place = ?, blood_group = ?, allergies = ?, relation = ?, email = ?
        WHERE app_id = ?
    """, (name, date_of_birth, gender, place, blood_group, allergies, relation, email, app_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Doctor helpers
# ---------------------------------------------------------------------------

def get_doctor_by_phone(phone_number):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM doctors WHERE phone_number = ?", (phone_number,)
    ).fetchone()
    conn.close()
    return row


def get_doctor_by_id(doctor_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,)
    ).fetchone()
    conn.close()
    return row


def create_doctor(phone_number, password_hash, name, email, hospital, speciality, location):
    doctor_id = generate_unique_doctor_id()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO doctors
        (doctor_id, phone_number, password_hash, name, email, hospital, speciality, location, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (doctor_id, phone_number, password_hash, name, email, hospital, speciality, location,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return doctor_id


def update_doctor_profile(doctor_id, hospital, location, email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE doctors
        SET hospital = ?, location = ?, email = ?
        WHERE doctor_id = ?
    """, (hospital, location, email, doctor_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def add_report(app_id, file_path, original_filename, report_date, tags):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reports (app_id, file_path, original_filename, report_date, tags, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (app_id, file_path, original_filename, report_date, tags, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_reports(app_id, search_term=None):
    conn = get_connection()
    if search_term:
        like = f"%{search_term.lower()}%"
        rows = conn.execute("""
            SELECT * FROM reports
            WHERE app_id = ?
            AND (LOWER(tags) LIKE ? OR LOWER(original_filename) LIKE ? OR LOWER(report_date) LIKE ?)
            ORDER BY report_date DESC
        """, (app_id, like, like, like)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reports WHERE app_id = ? ORDER BY report_date DESC",
            (app_id,)
        ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------

def add_prescription(app_id, file_path, original_filename, tags, added_by, added_by_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO prescriptions (app_id, file_path, original_filename, tags, added_by, added_by_id, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (app_id, file_path, original_filename, tags, added_by, added_by_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_prescriptions(app_id, search_term=None):
    conn = get_connection()
    if search_term:
        like = f"%{search_term.lower()}%"
        rows = conn.execute("""
            SELECT * FROM prescriptions
            WHERE app_id = ?
            AND (LOWER(tags) LIKE ? OR LOWER(original_filename) LIKE ?)
            ORDER BY added_at DESC
        """, (app_id, like, like)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM prescriptions WHERE app_id = ? ORDER BY added_at DESC",
            (app_id,)
        ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Medicine reminders
# ---------------------------------------------------------------------------

def add_medicine_reminder(app_id, medicine_name, dosage, timing, start_date, duration_days, everyday):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO medicine_reminders
        (app_id, medicine_name, dosage, timing, start_date, duration_days, everyday, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (app_id, medicine_name, dosage, timing, start_date, duration_days, int(everyday),
          datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_medicine_reminders(app_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM medicine_reminders WHERE app_id = ? ORDER BY created_at DESC",
        (app_id,)
    ).fetchall()
    conn.close()
    return rows


def delete_medicine_reminder(reminder_id):
    conn = get_connection()
    conn.execute("DELETE FROM medicine_reminders WHERE reminder_id = ?", (reminder_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

def add_followup(app_id, doctor_id, followup_date, followup_time, notes):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO followups (app_id, doctor_id, followup_date, followup_time, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (app_id, doctor_id, followup_date, followup_time, notes, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_followups(app_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, d.name as doctor_name, d.hospital as doctor_hospital
        FROM followups f
        JOIN doctors d ON f.doctor_id = d.doctor_id
        WHERE f.app_id = ?
        ORDER BY f.followup_date
    """, (app_id,)).fetchall()
    conn.close()
    return rows


def get_followups_by_doctor(doctor_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, fm.name as patient_name
        FROM followups f
        JOIN family_members fm ON f.app_id = fm.app_id
        WHERE f.doctor_id = ?
        ORDER BY f.followup_date
    """, (doctor_id,)).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# OTP (doctor record-access) helpers
# ---------------------------------------------------------------------------

def create_access_otp(app_id, doctor_id):
    otp_code = generate_otp_code()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO access_otps (app_id, doctor_id, otp_code, created_at)
        VALUES (?, ?, ?, ?)
    """, (app_id, doctor_id, otp_code, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return otp_code


def _is_otp_expired(created_at_str):
    try:
        created_at = datetime.fromisoformat(created_at_str)
    except (ValueError, TypeError):
        return True  # malformed timestamp - treat as expired/invalid, safest default
    return datetime.now() - created_at > timedelta(minutes=OTP_EXPIRY_MINUTES)


def cleanup_expired_otps():
    """Delete any OTPs older than the expiry window. Called opportunistically
    whenever OTPs are read, so stale ones don't linger in the database or UI."""
    conn = get_connection()
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()
    cur.execute("DELETE FROM access_otps WHERE created_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def get_pending_otps_for_app_id(app_id):
    """All not-yet-used, not-yet-expired OTPs currently outstanding for this
    patient (to show as alerts)."""
    cleanup_expired_otps()
    conn = get_connection()
    rows = conn.execute("""
        SELECT o.*, d.name as doctor_name, d.hospital as doctor_hospital
        FROM access_otps o
        JOIN doctors d ON o.doctor_id = d.doctor_id
        WHERE o.app_id = ?
        ORDER BY o.created_at DESC
    """, (app_id,)).fetchall()
    conn.close()
    return rows


def verify_and_consume_otp(app_id, doctor_id, otp_code):
    """
    Check OTP validity. Returns one of:
      'ok'      - correct and within the 5-minute window; OTP is now deleted (one-time use)
      'expired' - the code was correct but more than 5 minutes have passed; OTP is deleted
      'invalid' - no matching OTP found (wrong code, or already used/never existed)
    """
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT * FROM access_otps
        WHERE app_id = ? AND doctor_id = ? AND otp_code = ?
    """, (app_id, doctor_id, otp_code)).fetchone()

    if row is None:
        conn.close()
        return "invalid"

    expired = _is_otp_expired(row["created_at"])

    # Either way, this OTP is now spent - correct-but-expired codes shouldn't
    # remain usable, and correct-and-valid codes are one-time use.
    cur.execute("DELETE FROM access_otps WHERE otp_id = ?", (row["otp_id"],))
    conn.commit()
    conn.close()

    return "expired" if expired else "ok"


def discard_otp(otp_id):
    conn = get_connection()
    conn.execute("DELETE FROM access_otps WHERE otp_id = ?", (otp_id,))
    conn.commit()
    conn.close()
