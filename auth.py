"""
auth.py
Password hashing and login/registration logic for both doctors and
user accounts (phone + password, no OTP at login).
"""

import re
import bcrypt
import database as db

MAX_FAMILY_MEMBERS_PER_PHONE = 4


def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(plain_password, password_hash):
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def is_valid_phone(phone_number):
    """Basic validation: 10 digit Indian mobile number."""
    return bool(re.fullmatch(r"[6-9]\d{9}", phone_number.strip()))


def is_valid_password(password):
    return len(password) >= 6


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def is_valid_date_of_birth(dob_str):
    """dob_str expected as 'YYYY-MM-DD'; must not be in the future."""
    from datetime import datetime, date
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    return dob <= date.today()


# ---------------------------------------------------------------------------
# User (patient / family) side
# ---------------------------------------------------------------------------

def register_user_account(phone_number, password):
    """
    Creates a new account (phone + password). Returns (success, message, account_id).
    Note: this only creates the login credential. Family members are added afterwards.
    """
    phone_number = phone_number.strip()

    if not is_valid_phone(phone_number):
        return False, "Enter a valid 10-digit phone number.", None
    if not is_valid_password(password):
        return False, "Password must be at least 6 characters.", None

    existing = db.get_account_by_phone(phone_number)
    if existing is not None:
        return False, "An account already exists for this phone number. Please log in instead.", None

    pw_hash = hash_password(password)
    account_id = db.create_account(phone_number, pw_hash)
    return True, "Account created successfully.", account_id


def add_family_member_to_account(account_id, name, date_of_birth, gender, place, blood_group, allergies, relation, email=None):
    current_count = db.count_family_members(account_id)
    if current_count >= MAX_FAMILY_MEMBERS_PER_PHONE:
        return False, f"This phone number already has the maximum of {MAX_FAMILY_MEMBERS_PER_PHONE} family members.", None
    if not name or not name.strip():
        return False, "Name is required.", None
    if not is_valid_date_of_birth(date_of_birth):
        return False, "Enter a valid date of birth (cannot be in the future).", None
    if email and email.strip() and not is_valid_email(email):
        return False, "Enter a valid email address, or leave it blank.", None

    app_id = db.add_family_member(
        account_id, name.strip(), date_of_birth, gender, place, blood_group,
        allergies, relation, email.strip() if email else None
    )
    return True, f"Family member added. App ID: {app_id}", app_id


def login_user_account(phone_number, password):
    """Returns (success, message, account_row)."""
    phone_number = phone_number.strip()
    account = db.get_account_by_phone(phone_number)
    if account is None:
        return False, "No account found for this phone number.", None
    if not check_password(password, account["password_hash"]):
        return False, "Incorrect password.", None
    return True, "Login successful.", account


# ---------------------------------------------------------------------------
# Doctor side
# ---------------------------------------------------------------------------

def register_doctor(phone_number, password, name, email, hospital, speciality, location):
    phone_number = phone_number.strip()

    if not is_valid_phone(phone_number):
        return False, "Enter a valid 10-digit phone number.", None
    if not is_valid_password(password):
        return False, "Password must be at least 6 characters.", None
    if not name or not name.strip():
        return False, "Doctor name is required.", None
    if not email or not email.strip():
        return False, "Email is required for doctors.", None
    if not is_valid_email(email):
        return False, "Enter a valid email address.", None

    existing = db.get_doctor_by_phone(phone_number)
    if existing is not None:
        return False, "A doctor account already exists for this phone number. Please log in instead.", None

    pw_hash = hash_password(password)
    doctor_id = db.create_doctor(phone_number, pw_hash, name.strip(), email.strip(), hospital, speciality, location)
    return True, f"Doctor account created. Doctor ID: {doctor_id}", doctor_id


def update_doctor_profile(doctor_id, hospital, location, email):
    if not email or not email.strip():
        return False, "Email is required and cannot be left blank."
    if not is_valid_email(email):
        return False, "Enter a valid email address."

    db.update_doctor_profile(doctor_id, hospital, location, email.strip())
    return True, "Profile updated successfully."


def login_doctor(phone_number, password):
    phone_number = phone_number.strip()
    doctor = db.get_doctor_by_phone(phone_number)
    if doctor is None:
        return False, "No doctor account found for this phone number.", None
    if not check_password(password, doctor["password_hash"]):
        return False, "Incorrect password.", None
    return True, "Login successful.", doctor
