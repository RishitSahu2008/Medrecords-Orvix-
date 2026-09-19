"""
app.py
Main entry point. Run with:  streamlit run app.py

Handles:
  - Landing page (choose Login or Register)
  - Registration page with two tabs: Doctor / User & Family
  - Login page for both doctor and user (phone + password, no OTP)
  - Family member selection (for shared-phone accounts, max 4 members)
  - Routes to user_side.render_user_dashboard() or doctor_side.render_doctor_dashboard()
"""

import streamlit as st
from datetime import date

import database as db
import auth
import user_side
import doctor_side

st.set_page_config(page_title="MedRecords", page_icon="🩺", layout="wide")

db.init_db()


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

def init_session_state():
    defaults = {
        "page": "landing",          # landing | register | login
        "logged_in_role": None,     # 'user' | 'doctor'
        "account": None,            # account row (for user side)
        "doctor": None,             # doctor row (for doctor side)
        "selected_member": None,    # family member row (for user side)
        "doctor_access_app_id": None,
        "otp_requested_for": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def logout():
    for key in ["logged_in_role", "account", "doctor", "selected_member",
                "doctor_access_app_id", "otp_requested_for"]:
        st.session_state[key] = None
    st.session_state.page = "landing"


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

def render_landing():
    st.title("🩺 MedRecords")
    st.write("All your family's medical records, appointments and reminders — in one place.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()
    with col2:
        if st.button("Register", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()


# ---------------------------------------------------------------------------
# Registration page
# ---------------------------------------------------------------------------

def render_register():
    st.title("Create an Account")
    if st.button("← Back"):
        st.session_state.page = "landing"
        st.rerun()

    tab_doctor, tab_user = st.tabs(["Doctor Registration", "User / Family Registration"])

    with tab_doctor:
        with st.form("doctor_register_form"):
            phone = st.text_input("Phone Number (10 digits)")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            name = st.text_input("Doctor Name")
            email = st.text_input("Email *(required)*")
            hospital = st.text_input("Hospital / Clinic")
            speciality = st.text_input("Speciality")
            location = st.text_input("Location")
            submitted = st.form_submit_button("Register as Doctor")

            if submitted:
                if password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    ok, msg, doctor_id = auth.register_doctor(
                        phone, password, name, email, hospital, speciality, location
                    )
                    if ok:
                        st.success(msg + "  You can now log in.")
                    else:
                        st.error(msg)

    with tab_user:
        st.markdown("#### Step 1: Create login (phone + password)")
        with st.form("user_register_form"):
            phone = st.text_input("Phone Number (10 digits)", key="ureg_phone")
            password = st.text_input("Password", type="password", key="ureg_pass")
            confirm_password = st.text_input("Confirm Password", type="password", key="ureg_pass2")
            submitted = st.form_submit_button("Create Account")

            if submitted:
                if password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    ok, msg, account_id = auth.register_user_account(phone, password)
                    if ok:
                        st.success(msg + " Now log in to add family members.")
                    else:
                        st.error(msg)


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

def render_login():
    st.title("Login")
    if st.button("← Back"):
        st.session_state.page = "landing"
        st.rerun()

    tab_doctor, tab_user = st.tabs(["Doctor Login", "User / Family Login"])

    with tab_doctor:
        with st.form("doctor_login_form"):
            phone = st.text_input("Phone Number")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                ok, msg, doctor = auth.login_doctor(phone, password)
                if ok:
                    st.session_state.logged_in_role = "doctor"
                    st.session_state.doctor = dict(doctor)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_user:
        with st.form("user_login_form"):
            phone = st.text_input("Phone Number", key="ulog_phone")
            password = st.text_input("Password", type="password", key="ulog_pass")
            submitted = st.form_submit_button("Login")
            if submitted:
                ok, msg, account = auth.login_user_account(phone, password)
                if ok:
                    st.session_state.logged_in_role = "user"
                    st.session_state.account = dict(account)
                    st.rerun()
                else:
                    st.error(msg)


# ---------------------------------------------------------------------------
# Family member selection (after user login)
# ---------------------------------------------------------------------------

def render_family_selection():
    account = st.session_state.account
    st.title("Who's using the app?")

    members = db.get_family_members(account["account_id"])

    if members:
        cols = st.columns(min(4, len(members)))
        for i, member in enumerate(members):
            with cols[i % len(cols)]:
                st.markdown(f"**{member['name']}**")
                computed_age = db.calculate_age(member["date_of_birth"])
                age_label = f"{computed_age} yrs" if computed_age is not None else "Age not set"
                st.caption(f"{member['relation'] or ''} • {age_label}")
                if st.button("Select", key=f"select_{member['app_id']}"):
                    st.session_state.selected_member = dict(member)
                    st.rerun()

    if len(members) < auth.MAX_FAMILY_MEMBERS_PER_PHONE:
        st.markdown("---")
        with st.expander(f"+ Add a family member ({len(members)}/{auth.MAX_FAMILY_MEMBERS_PER_PHONE} used)"):
            with st.form("add_family_member_form", clear_on_submit=True):
                name = st.text_input("Name")
                date_of_birth = st.date_input(
                    "Date of Birth", min_value=date(1900, 1, 1), max_value=date.today(), value=date(2000, 1, 1)
                )
                gender = st.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"])
                place = st.text_input("Place")
                blood_group = st.selectbox(
                    "Blood Group", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"]
                )
                allergies = st.text_area("Allergies")
                relation = st.text_input("Relation (e.g. self, spouse, child)")
                email = st.text_input("Email (optional)")
                submitted = st.form_submit_button("Add Family Member")

                if submitted:
                    ok, msg, app_id = auth.add_family_member_to_account(
                        account["account_id"], name, str(date_of_birth), gender, place,
                        blood_group, allergies, relation, email
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.info("Maximum of 4 family members already added for this phone number.")

    st.markdown("---")
    if st.button("Logout"):
        logout()
        st.rerun()


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def main():
    init_session_state()

    # Sidebar logout, shown whenever logged in
    if st.session_state.logged_in_role:
        with st.sidebar:
            if st.session_state.logged_in_role == "doctor":
                st.write(f"Logged in as **Dr. {st.session_state.doctor['name']}**")
            elif st.session_state.selected_member:
                st.write(f"Profile: **{st.session_state.selected_member['name']}**")
                if st.button("Switch Family Member"):
                    st.session_state.selected_member = None
                    st.rerun()
            if st.button("Logout"):
                logout()
                st.rerun()

    # Routing
    if st.session_state.logged_in_role == "doctor":
        doctor_side.render_doctor_dashboard(st.session_state.doctor)

    elif st.session_state.logged_in_role == "user":
        if st.session_state.selected_member is None:
            render_family_selection()
        else:
            # Keep selected_member fresh (in case basic info was just edited)
            fresh = db.get_family_member(st.session_state.selected_member["app_id"])
            st.session_state.selected_member = dict(fresh)
            user_side.render_user_dashboard(st.session_state.selected_member)

    else:
        if st.session_state.page == "register":
            render_register()
        elif st.session_state.page == "login":
            render_login()
        else:
            render_landing()


if __name__ == "__main__":
    main()
