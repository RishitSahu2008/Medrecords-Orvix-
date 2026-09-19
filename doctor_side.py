"""
doctor_side.py
Doctor home page (own profile) and the OTP-gated patient record access
flow: request access -> patient shares OTP -> doctor enters OTP ->
view records / add prescription / set follow-up.
"""

import streamlit as st
from datetime import date

import database as db
import storage
import auth


def render_doctor_home(doctor):
    st.title(f"🩺 Dr. {doctor['name']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Speciality", doctor["speciality"] or "—")
    col2.metric("Hospital / Clinic", doctor["hospital"] or "—")
    col3.metric("Location", doctor["location"] or "—")
    st.caption(f"Doctor ID: `{doctor['doctor_id']}`  •  Email: {doctor['email'] or 'Not set'}")

    with st.expander("Edit Profile"):
        with st.form("edit_doctor_profile_form"):
            st.caption("Speciality cannot be changed after registration.")
            hospital = st.text_input("Hospital / Clinic", value=doctor["hospital"] or "")
            location = st.text_input("Location", value=doctor["location"] or "")
            email = st.text_input("Email *(required)*", value=doctor["email"] or "")
            submitted = st.form_submit_button("Save Profile")

            if submitted:
                ok, msg = auth.update_doctor_profile(doctor["doctor_id"], hospital, location, email)
                if ok:
                    st.success(msg)
                    # Refresh the in-session doctor record so the page reflects changes immediately
                    st.session_state.doctor = dict(db.get_doctor_by_id(doctor["doctor_id"]))
                    st.rerun()
                else:
                    st.error(msg)


def render_patient_access_flow(doctor):
    st.markdown("---")
    st.subheader("Access a Patient's Records")

    if "otp_requested_for" not in st.session_state:
        st.session_state.otp_requested_for = None

    # Step 1: enter App ID, request OTP
    with st.form("request_access_form"):
        app_id_input = st.text_input("Patient App ID").strip().upper()
        request_btn = st.form_submit_button("Request Access (send OTP)")

        if request_btn:
            member = db.get_family_member(app_id_input)
            if member is None:
                st.error("No patient found with that App ID.")
            else:
                otp = db.create_access_otp(app_id_input, doctor["doctor_id"])
                st.session_state.otp_requested_for = app_id_input
                st.success(
                    f"An OTP has been generated for **{member['name']}**. "
                    "Ask the patient to check their 'Follow-Up Alerts'/home alert panel "
                    f"on their app and share the OTP with you. **It expires in {db.OTP_EXPIRY_MINUTES} minutes.**"
                )

    # Step 2: enter OTP to unlock records
    if st.session_state.otp_requested_for:
        target_app_id = st.session_state.otp_requested_for
        with st.form("verify_otp_form"):
            st.write(f"Enter the OTP given to you by the patient (App ID: `{target_app_id}`)")
            otp_input = st.text_input("OTP", max_chars=6)
            verify_btn = st.form_submit_button("Verify & Open Records")

            if verify_btn:
                result = db.verify_and_consume_otp(target_app_id, doctor["doctor_id"], otp_input.strip())
                if result == "ok":
                    st.session_state.doctor_access_app_id = target_app_id
                    st.session_state.otp_requested_for = None
                    st.success("Access granted.")
                    st.rerun()
                elif result == "expired":
                    st.error(
                        f"That OTP has expired (valid for only {db.OTP_EXPIRY_MINUTES} minutes). "
                        "Please request a new one."
                    )
                    st.session_state.otp_requested_for = None
                else:
                    st.error("Incorrect OTP. Please check with the patient and try again.")


def render_patient_record_view(doctor, app_id):
    member = db.get_family_member(app_id)
    if member is None:
        st.error("Patient not found.")
        return

    st.markdown("---")
    st.subheader(f"Records: {member['name']}  (`{app_id}`)")

    if st.button("Close patient records"):
        st.session_state.doctor_access_app_id = None
        st.rerun()

    tabs = st.tabs(["Basic Info", "Reports", "Prescriptions", "Add Prescription", "Set Follow-Up"])

    with tabs[0]:
        st.write(f"**Name:** {member['name']}")
        computed_age = db.calculate_age(member["date_of_birth"])
        st.write(f"**Age:** {computed_age if computed_age is not None else 'Not set'}")
        st.write(f"**Gender:** {member['gender'] or 'Not specified'}")
        st.write(f"**Place:** {member['place']}")
        st.write(f"**Blood Group:** {member['blood_group']}")
        st.write(f"**Allergies:** {member['allergies'] or 'None recorded'}")

    with tabs[1]:
        reports = db.get_reports(app_id)
        if not reports:
            st.info("No reports on file.")
        for r in reports:
            with st.expander(f"{r['original_filename']} — {r['report_date']}"):
                st.write(f"**Tags:** {r['tags'] or '—'}")
                try:
                    with open(storage.get_file_path(r["file_path"]), "rb") as f:
                        st.download_button(
                            "Download / View PDF", data=f.read(),
                            file_name=r["original_filename"], mime="application/pdf",
                            key=f"doc_dl_report_{r['report_id']}"
                        )
                except FileNotFoundError:
                    st.error("File not found in storage.")

    with tabs[2]:
        prescriptions = db.get_prescriptions(app_id)
        if not prescriptions:
            st.info("No prescriptions on file.")
        for p in prescriptions:
            added_by_label = "Doctor" if p["added_by"] == "doctor" else "Patient"
            with st.expander(f"{p['original_filename']} — added by {added_by_label}"):
                st.write(f"**Tags:** {p['tags'] or '—'}")
                try:
                    st.image(storage.get_file_path(p["file_path"]))
                except Exception:
                    st.error("Could not load image.")

    with tabs[3]:
        with st.form("doctor_add_prescription_form", clear_on_submit=True):
            uploaded_file = st.file_uploader("Upload prescription image", type=["png", "jpg", "jpeg"])
            tags = st.text_input("Tags (comma-separated)")
            submitted = st.form_submit_button("Add Prescription")
            if submitted:
                if uploaded_file is None:
                    st.error("Please choose an image to upload.")
                else:
                    path = storage.save_file(app_id, "prescriptions", uploaded_file)
                    db.add_prescription(app_id, path, uploaded_file.name, tags,
                                         added_by="doctor", added_by_id=doctor["doctor_id"])
                    st.success("Prescription added to patient's record.")

    with tabs[4]:
        with st.form("set_followup_form", clear_on_submit=True):
            followup_date = st.date_input("Follow-up date", value=date.today())
            followup_time = st.text_input("Follow-up time (e.g. 10:30 AM)")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Set Follow-Up")
            if submitted:
                db.add_followup(app_id, doctor["doctor_id"], str(followup_date), followup_time, notes)
                st.success("Follow-up reminder set. The patient will see it as an alert.")


def render_my_patients_tab(doctor):
    st.subheader("My Patients & Follow-Ups")
    st.caption("Every follow-up you've set, across all your patients.")

    all_followups = db.get_followups_by_doctor(doctor["doctor_id"])

    if not all_followups:
        st.info("You haven't set any follow-ups yet. They'll show up here once you do.")
        return

    today = date.today()
    upcoming = [f for f in all_followups if date.fromisoformat(f["followup_date"]) >= today]
    past = [f for f in all_followups if date.fromisoformat(f["followup_date"]) < today]

    upcoming.sort(key=lambda f: f["followup_date"])
    past.sort(key=lambda f: f["followup_date"], reverse=True)

    st.markdown(f"#### Upcoming ({len(upcoming)})")
    if not upcoming:
        st.caption("No upcoming follow-ups.")
    for f in upcoming:
        is_today = f["followup_date"] == str(today)
        label = "**Today**" if is_today else f["followup_date"]
        box = st.warning if is_today else st.info
        box(
            f"{label} {f['followup_time'] or ''} — **{f['patient_name']}** (`{f['app_id']}`)\n\n"
            f"{f['notes'] or 'No notes'}"
        )

    st.markdown(f"#### Past ({len(past)})")
    if not past:
        st.caption("No past follow-ups.")
    for f in past:
        with st.expander(f"{f['followup_date']} {f['followup_time'] or ''} — {f['patient_name']} (`{f['app_id']}`)"):
            st.write(f["notes"] or "No notes")


def render_doctor_dashboard(doctor):
    render_doctor_home(doctor)

    st.markdown("---")
    tab_access, tab_patients = st.tabs(["Access Patient Records", "My Patients & Follow-Ups"])

    with tab_access:
        if st.session_state.get("doctor_access_app_id"):
            render_patient_record_view(doctor, st.session_state.doctor_access_app_id)
        else:
            render_patient_access_flow(doctor)

    with tab_patients:
        render_my_patients_tab(doctor)
