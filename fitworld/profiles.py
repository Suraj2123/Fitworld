"""Profile changes and explicit weight intent, separate from HTTP/session handling."""

from datetime import datetime, timezone

from .measurements import upsert_measurement
from .validation import ValidationError, iso_date, preferences, profile


def save_profile(connection, user_id, data):
    age, kilograms, units, experience, frequency = profile(data)
    weight_intent = data.get("record_weight")
    if weight_intent is not None and not isinstance(weight_intent, bool):
        raise ValidationError({"record_weight": "Choose whether this is a new weight check-in."})
    # Older clients omitted the date. Preserve that contract; current clients send local dates.
    measured_on = iso_date(
        data.get("measured_on", datetime.now(timezone.utc).date().isoformat()),
        "measured_on",
        historical=True,
    )
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            "SELECT weight_kg FROM user_profiles WHERE user_id=?", (user_id,)
        ).fetchone()
        record_weight = previous is None or (
            weight_intent if weight_intent is not None else kilograms != previous["weight_kg"]
        )
        stored_weight = kilograms if record_weight else previous["weight_kg"]
        connection.execute(
            """INSERT INTO user_profiles
               (user_id, age, weight_kg, unit_system, experience_level, current_workouts_per_week)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET age=excluded.age, weight_kg=excluded.weight_kg,
               unit_system=excluded.unit_system, experience_level=excluded.experience_level,
               current_workouts_per_week=excluded.current_workouts_per_week, updated_at=CURRENT_TIMESTAMP""",
            (user_id, age, stored_weight, units, experience, frequency),
        )
        if record_weight:
            upsert_measurement(connection, user_id, kilograms, measured_on)


def save_preferences(connection, user_id, data):
    goal, location, days, minutes = preferences(data)
    with connection:
        connection.execute(
            """INSERT INTO workout_preferences
               (user_id, primary_goal, training_location, target_days_per_week, session_minutes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET primary_goal=excluded.primary_goal,
               training_location=excluded.training_location, target_days_per_week=excluded.target_days_per_week,
               session_minutes=excluded.session_minutes, updated_at=CURRENT_TIMESTAMP""",
            (user_id, goal, location, days, minutes),
        )
