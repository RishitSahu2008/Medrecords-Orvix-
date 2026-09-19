"""
user_side.py
Everything rendered after a patient (family member) logs in and selects
their profile: basic info, reports, prescriptions, medicine reminders,
and follow-up alerts.
"""

import streamlit as st
from datetime import date

import database as db
import storage
import reminders as R


def render_pending_otp_alerts(app_id):
    """Show any doctor access requests (OTPs) waiting for this patient - our
    stand-in for 'the OTP was sent to the patient's phone'."""
    pending = db.get_pending_otps_for_app_id(app_id)
    if pending:
        st.warning("**Doctor access request(s) pending** — share this OTP only if you recognize the doctor.")
        for p in pending:
            st.info(
                f"Dr. **{p['doctor_name']}** ({p['doctor_hospital'] or 'Hospital not set'}) "
                f"is requesting access to your records.\n\n**OTP: `{p['otp_code']}`**  "
                f"*(expires {db.OTP_EXPIRY_MINUTES} minutes after it was requested)*"
            )


def render_basic_info_tab(member):
    st.subheader("Basic Information")

    # Parse existing DOB (fallback to a sensible default if missing/invalid)
    try:
        current_dob = date.fromisoformat(member["date_of_birth"]) if member["date_of_birth"] else date(2000, 1, 1)
    except (ValueError, TypeError):
        current_dob = date(2000, 1, 1)

    with st.form("basic_info_form"):
        name = st.text_input("Name", value=member["name"])
        date_of_birth = st.date_input(
            "Date of Birth", min_value=date(1900, 1, 1), max_value=date.today(), value=current_dob
        )
        computed_age = db.calculate_age(str(date_of_birth))
        st.caption(f"Current age (calculated automatically): **{computed_age} years**")

        gender_options = ["Male", "Female", "Other", "Prefer not to say"]
        current_gender = member["gender"] if member["gender"] in gender_options else "Prefer not to say"
        gender = st.selectbox("Gender", gender_options, index=gender_options.index(current_gender))
        place = st.text_input("Place", value=member["place"] or "")
        blood_group = st.selectbox(
            "Blood Group",
            ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"],
            index=(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"].index(member["blood_group"])
                   if member["blood_group"] in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"] else 8)
        )
        allergies = st.text_area("Allergies", value=member["allergies"] or "")
        relation = st.text_input("Relation (e.g. self, spouse, child)", value=member["relation"] or "")
        email = st.text_input("Email (optional)", value=member["email"] or "")

        submitted = st.form_submit_button("Save Changes")
        if submitted:
            if email and email.strip():
                import re
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
                    st.error("Enter a valid email address, or leave it blank.")
                    st.stop()
            db.update_basic_info(
                member["app_id"], name, str(date_of_birth), gender, place,
                blood_group, allergies, relation, email.strip() if email else None
            )
            st.success("Basic info updated.")
            st.rerun()

    st.caption(f"App ID: `{member['app_id']}`  •  Share this ID with your doctor for record access.")


def render_add_report_tab(app_id):
    st.subheader("Add a Report")
    with st.form("add_report_form", clear_on_submit=True):
        uploaded_file = st.file_uploader("Upload report (PDF)", type=["pdf"])
        report_date = st.date_input("Date of report / diagnosis", value=date.today())
        tags = st.text_input("Tags (comma-separated, e.g. blood test, sugar, routine)")
        submitted = st.form_submit_button("Upload Report")

        if submitted:
            if uploaded_file is None:
                st.error("Please choose a PDF file to upload.")
            else:
                path = storage.save_file(app_id, "reports", uploaded_file)
                db.add_report(app_id, path, uploaded_file.name, str(report_date), tags)
                st.success("Report uploaded successfully.")


def render_view_reports_tab(app_id):
    st.subheader("View Reports")
    search_term = st.text_input("Search reports by tag, filename, or date", key="report_search")
    results = db.get_reports(app_id, search_term if search_term else None)

    if not results:
        st.info("No reports found.")
        return

    for r in results:
        with st.expander(f"{r['original_filename']}  —  {r['report_date']}"):
            st.write(f"**Tags:** {r['tags'] or '—'}")
            st.write(f"**Uploaded:** {r['uploaded_at'][:16].replace('T', ' ')}")
            try:
                with open(storage.get_file_path(r["file_path"]), "rb") as f:
                    st.download_button(
                        "Download / View PDF",
                        data=f.read(),
                        file_name=r["original_filename"],
                        mime="application/pdf",
                        key=f"dl_report_{r['report_id']}",
                    )
            except FileNotFoundError:
                st.error("File not found in storage.")


def render_prescriptions_tab(app_id):
    st.subheader("Prescriptions")

    with st.expander("+ Add a prescription"):
        with st.form("add_prescription_form", clear_on_submit=True):
            uploaded_file = st.file_uploader("Upload prescription image", type=["png", "jpg", "jpeg"])
            tags = st.text_input("Tags (comma-separated)")
            submitted = st.form_submit_button("Upload Prescription")
            if submitted:
                if uploaded_file is None:
                    st.error("Please choose an image to upload.")
                else:
                    path = storage.save_file(app_id, "prescriptions", uploaded_file)
                    db.add_prescription(app_id, path, uploaded_file.name, tags, added_by="user")
                    st.success("Prescription uploaded.")

    search_term = st.text_input("Search prescriptions by tag or filename", key="presc_search")
    results = db.get_prescriptions(app_id, search_term if search_term else None)

    if not results:
        st.info("No prescriptions found.")
        return

    for p in results:
        added_by_label = "Doctor" if p["added_by"] == "doctor" else "You"
        with st.expander(f"{p['original_filename']}  —  added by {added_by_label}"):
            st.write(f"**Tags:** {p['tags'] or '—'}")
            st.write(f"**Added:** {p['added_at'][:16].replace('T', ' ')}")
            try:
                st.image(storage.get_file_path(p["file_path"]))
            except Exception:
                st.error("Could not load image.")


def render_medicine_reminder_tab(app_id):
    st.subheader("Medicine Reminders")

    with st.expander("+ Add a medicine reminder"):
        with st.form("add_medicine_form", clear_on_submit=True):
            medicine_name = st.text_input("Medicine name")
            dosage = st.text_input("Dosage (e.g. 500mg, 1 tablet)")
            timing_options = st.multiselect(
                "When to take",
                ["Before Breakfast", "After Breakfast", "Before Lunch", "After Lunch",
                 "Before Dinner", "After Dinner", "Bedtime"]
            )
            everyday = st.checkbox("Take every day (ongoing, no end date)")
            duration_days = None
            if not everyday:
                duration_days = st.number_input("Number of days to remind", min_value=1, max_value=365, value=5)
            start_date = st.date_input("Start date", value=date.today())

            submitted = st.form_submit_button("Add Reminder")
            if submitted:
                if not medicine_name.strip():
                    st.error("Medicine name is required.")
                else:
                    db.add_medicine_reminder(
                        app_id, medicine_name.strip(), dosage,
                        ", ".join(timing_options), str(start_date),
                        int(duration_days) if duration_days else None,
                        everyday
                    )
                    st.success("Reminder added.")
                    st.rerun()

    st.markdown("#### Active Reminders (today)")
    all_reminders = db.get_medicine_reminders(app_id)
    active = R.active_medicine_reminders(all_reminders)

    if not active:
        st.info("No medicine reminders are active today.")
    else:
        for r in active:
            st.success(
                f"**{r['medicine_name']}** ({r['dosage'] or 'dosage not set'}) — {r['timing'] or 'timing not set'}"
            )

    st.markdown("#### All Reminders")
    if not all_reminders:
        st.caption("No reminders added yet.")
    for r in all_reminders:
        cols = st.columns([5, 1])
        duration_label = "Every day" if r["everyday"] else f"{r['duration_days']} day(s) from {r['start_date']}"
        cols[0].write(f"**{r['medicine_name']}** — {r['dosage'] or '—'} — {r['timing'] or '—'} — {duration_label}")
        if cols[1].button("Delete", key=f"del_med_{r['reminder_id']}"):
            db.delete_medicine_reminder(r["reminder_id"])
            st.rerun()


def render_followup_tab(app_id):
    st.subheader("Follow-Up Alerts")
    st.caption("Follow-up dates are set by your doctor. This is a read-only view.")

    all_followups = db.get_followups(app_id)
    upcoming = R.upcoming_followups(all_followups)

    if not upcoming:
        st.info("No upcoming or recent follow-ups.")
    else:
        for f, delta in upcoming:
            if delta < 0:
                st.error(f"**Missed follow-up** with Dr. {f['doctor_name']} on {f['followup_date']} ({f['followup_time'] or ''}) — {f['notes'] or ''}")
            elif delta == 0:
                st.warning(f"**Today:** Follow-up with Dr. {f['doctor_name']} at {f['followup_time'] or 'time not set'} — {f['notes'] or ''}")
            else:
                st.info(f"In {delta} day(s): Follow-up with Dr. {f['doctor_name']} on {f['followup_date']} ({f['followup_time'] or ''}) — {f['notes'] or ''}")

    st.markdown("#### Full Follow-Up History")
    if not all_followups:
        st.caption("No follow-ups recorded yet.")
    for f in all_followups:
        st.write(f"- {f['followup_date']} {f['followup_time'] or ''} — Dr. {f['doctor_name']} ({f['doctor_hospital'] or '—'}): {f['notes'] or 'No notes'}")


def render_user_dashboard(member):
    app_id = member["app_id"]

    st.title(f"👤 {member['name']}")
    render_pending_otp_alerts(app_id)

    tabs = st.tabs([
        "Basic Info", "Add Report", "View Reports",
        "Prescriptions", "Medicine Reminders", "Follow-Up Alerts"
    ])

    with tabs[0]:
        render_basic_info_tab(member)
    with tabs[1]:
        render_add_report_tab(app_id)
    with tabs[2]:
        render_view_reports_tab(app_id)
    with tabs[3]:
        render_prescriptions_tab(app_id)
    with tabs[4]:
        render_medicine_reminder_tab(app_id)
    with tabs[5]:
        render_followup_tab(app_id)
