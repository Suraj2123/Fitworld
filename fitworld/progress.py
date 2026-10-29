"""Calendar and personal progress read models, independent of page rendering."""

import calendar
import re
from datetime import date, timedelta

from .activity import iso_date
from .validation import Form, ValidationError, body_weight


def month_range(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise ValidationError({"month": "Choose a month in YYYY-MM format."})
    year, month = map(int, value.split("-"))
    if not 1900 <= year <= 2100:
        raise ValidationError({"month": "Choose a month between 1900 and 2100."})
    first = date(year, month, 1)
    count = calendar.monthrange(year, month)[1]
    return first, first + timedelta(days=count)


def exercise_records(connection, user_id, start, end):
    # A stable exercise ID unifies renamed catalog entries; snapshots cover deleted exercises.
    rows = connection.execute("""
        SELECT COALESCE('id:' || e.exercise_id, 'name:' || lower(trim(e.exercise_name))) AS exercise_key,
               MAX(e.exercise_name) AS name,
               MAX(CASE WHEN w.performed_on < :start THEN e.load_kg END) AS previous_load,
               MAX(CASE WHEN w.performed_on >= :start THEN e.load_kg END) AS current_load,
               MAX(CASE WHEN w.performed_on < :start THEN e.duration_seconds END) AS previous_seconds,
               MAX(CASE WHEN w.performed_on >= :start THEN e.duration_seconds END) AS current_seconds
        FROM exercise_logs e JOIN workout_logs w ON w.id=e.workout_log_id
        WHERE w.user_id=:user AND w.status='completed' AND w.performed_on < :end
        GROUP BY exercise_key
    """, {"user": user_id, "start": start, "end": end}).fetchall()
    result = []
    for row in rows:
        for metric, key in (("load_kg", "load"), ("duration_seconds", "seconds")):
            value, previous = row[f"current_{key}"], row[f"previous_{key}"]
            if value is not None:
                result.append({"exercise_key": row["exercise_key"], "name": row["name"], "metric": metric, "value": value, "previous_best": previous, "improvement": round(value - previous, 3) if previous is not None and value > previous else None})
    return sorted(result, key=lambda item: (item["improvement"] is None, item["name"], item["metric"]))


def monthly_progress(connection, user_id, month, today):
    first, end = month_range(month)
    start_text, end_text = first.isoformat(), end.isoformat()
    days = {}
    for offset in range((end - first).days):
        current = (first + timedelta(days=offset)).isoformat()
        days[current] = {"date": current, "completed": 0, "partial": 0, "minutes": 0, "workouts": [], "meals": 0}
    workouts = connection.execute("SELECT performed_on, workout_name, status, duration_seconds FROM workout_logs WHERE user_id=? AND performed_on>=? AND performed_on<? ORDER BY performed_on, started_at, id", (user_id, start_text, end_text)).fetchall()
    for row in workouts:
        day = days.get(row["performed_on"])
        if day is None:  # Legacy clients may have written noncanonical text dates.
            continue
        day[row["status"]] += 1
        day["minutes"] += row["duration_seconds"] / 60
        day["workouts"].append({"name": row["workout_name"], "status": row["status"]})
    for row in connection.execute("SELECT consumed_on, COUNT(*) AS meals FROM nutrition_logs WHERE user_id=? AND consumed_on>=? AND consumed_on<? GROUP BY consumed_on", (user_id, start_text, end_text)):
        if row["consumed_on"] in days:
            days[row["consumed_on"]]["meals"] = row["meals"]
    completed = sum(day["completed"] for day in days.values())
    as_of = date.fromisoformat(today)
    elapsed = (as_of - first).days + 1 if first <= as_of < end else (end - first).days
    measurements = [dict(row) for row in connection.execute("SELECT measured_on, weight_kg FROM body_measurements WHERE user_id=? AND measured_on<? ORDER BY measured_on DESC LIMIT 30", (user_id, end_text))][::-1]
    milestones = [dict(row) for row in connection.execute("SELECT id, title, description, achieved_on FROM milestones WHERE user_id=? AND achieved_on>=? AND achieved_on<? ORDER BY achieved_on DESC, id DESC", (user_id, start_text, end_text))]
    return {
        "month": month, "starts_on": start_text, "ends_on": (end - timedelta(days=1)).isoformat(),
        "summary": {
            "completed_workouts": completed,
            "partial_workouts": sum(day["partial"] for day in days.values()),
            "active_days": sum(bool(day["completed"] or day["partial"]) for day in days.values()),
            "duration_minutes": round(sum(day["minutes"] for day in days.values()), 1),
            "average_per_week": round(completed * 7 / elapsed, 1),
            "average_window_days": elapsed,
            "average_window": "month_to_date" if first <= as_of < end else "full_month",
        },
        "days": list(days.values()), "records": exercise_records(connection, user_id, start_text, end_text),
        "measurements": measurements, "milestones": milestones,
    }


def record_weight(connection, user_id, data):
    form = Form(data)
    kilograms, _units = body_weight(form)
    form.finish()
    measured_on = iso_date(data.get("measured_on"), "measured_on", historical=True)
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO body_measurements (user_id, measured_on, weight_kg) VALUES (?, ?, ?) ON CONFLICT(user_id, measured_on) DO UPDATE SET weight_kg=excluded.weight_kg", (user_id, measured_on, kilograms))
        latest = connection.execute("SELECT weight_kg FROM body_measurements WHERE user_id=? ORDER BY measured_on DESC LIMIT 1", (user_id,)).fetchone()
        connection.execute("UPDATE user_profiles SET weight_kg=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (latest["weight_kg"], user_id))
    return {"measured_on": measured_on, "weight_kg": kilograms}
