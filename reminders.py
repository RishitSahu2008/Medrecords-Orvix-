"""
reminders.py
Pure logic (no UI) for figuring out which medicine reminders are
currently active and which follow-ups count as "upcoming" alerts.
"""

from datetime import date, datetime, timedelta


def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def is_medicine_active_today(reminder_row, today=None):
    """
    A medicine reminder is 'active today' if:
      - it is marked 'everyday' (ongoing, no end date), OR
      - today falls within [start_date, start_date + duration_days - 1]
    """
    if today is None:
        today = date.today()

    start = parse_date(reminder_row["start_date"])

    if reminder_row["everyday"]:
        return start <= today

    duration = reminder_row["duration_days"] or 0
    if duration <= 0:
        return start <= today  # fallback: treat as ongoing if no duration given

    end = start + timedelta(days=duration - 1)
    return start <= today <= end


def active_medicine_reminders(all_reminders, today=None):
    return [r for r in all_reminders if is_medicine_active_today(r, today)]


def upcoming_followups(all_followups, days_ahead=14, today=None):
    """
    Return follow-ups that are today, in the future within `days_ahead`,
    or were missed in the recent past (still worth alerting about).
    """
    if today is None:
        today = date.today()

    result = []
    for f in all_followups:
        f_date = parse_date(f["followup_date"])
        delta = (f_date - today).days
        if -3 <= delta <= days_ahead:  # show recently missed (up to 3 days) + upcoming
            result.append((f, delta))
    result.sort(key=lambda pair: pair[1])
    return result
