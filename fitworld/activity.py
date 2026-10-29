"""Validate and persist user activity atomically. HTTP and UI code contain no SQL."""

from datetime import date, datetime, timedelta, timezone

from werkzeug.exceptions import BadRequest, Conflict, NotFound

from .catalog import workout_detail
from .validation import Form, ValidationError


def iso_date(value, field="date", historical=False):
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        if not 1900 <= parsed.year <= 2100:
            raise ValueError
        if historical and parsed > datetime.now(timezone.utc).date() + timedelta(days=1):
            raise ValueError
        return value
    except (ValueError, TypeError):
        message = "Choose a valid date from 1900–2100 (YYYY-MM-DD)." if not historical else "Choose a valid date for an entry that has already happened (1900–2100)."
        raise ValidationError({field: message}) from None


def optional_number(form, key, label, maximum, integer=False):
    if form.data.get(key) in (None, ""):
        return None
    return form.number(key, label, 0, maximum, integer=integer)


def log_workout(connection, user_id, data):
    form = Form(data)
    workout_id = None if data.get("workout_id") in (None, "") else form.number("workout_id", "workout", 1, 2**53, integer=True)
    workout_name = form.text("workout_name", "Workout name", 120) if workout_id is None else None
    minutes = form.number("duration_minutes", "workout duration", 1 if workout_id is None else 0, 1440, integer=workout_id is None)
    status = form.choice("status", {"completed", "partial"}, "completed or stopped early")
    calories = optional_number(form, "estimated_calories", "estimated calories", 50000)
    notes = form.text("notes", "Notes", 2000, minimum=0) if data.get("notes") is not None else ""
    scheduled_id = optional_number(form, "scheduled_workout_id", "scheduled workout", 2**53, integer=True)
    form.finish()
    performed_on = iso_date(data.get("performed_on"), "performed_on", historical=True)
    workout = workout_detail(connection, workout_id) if workout_id is not None else {"name": workout_name, "exercises": []}
    valid_exercises = {row["exercise_id"]: row for row in workout["exercises"]}
    raw_exercises = data.get("exercises", [])
    if not isinstance(raw_exercises, list) or len(raw_exercises) > 200:
        raise ValidationError({"exercises": "Add at most 200 exercise sets."})
    exercises = []
    for item in raw_exercises:
        if not isinstance(item, dict):
            raise ValidationError({"exercises": "Each exercise set must contain exercise details."})
        entry = Form(item)
        exercise_id = entry.number("exercise_id", "exercise", 1, 2**53, integer=True)
        reps = optional_number(entry, "reps", "reps", 10000, integer=True)
        seconds = optional_number(entry, "duration_seconds", "exercise duration", 86400, integer=True)
        load = optional_number(entry, "load_kg", "load in kilograms", 2000)
        number = entry.number("set_number", "set number", 1, 200, integer=True)
        if reps is None and seconds is None:
            entry.errors["exercises"] = "Each saved set needs actual reps or a duration. Leave unrecorded sets empty."
        if exercise_id not in valid_exercises:
            entry.errors["exercises"] = "Choose exercises from the selected workout."
        if entry.errors:
            raise ValidationError({"exercises": " ".join(entry.errors.values())})
        definition = valid_exercises[exercise_id]
        exercises.append((exercise_id, definition["name"], definition["muscle_group"], number, reps, seconds, load))
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if scheduled_id is not None:
            scheduled = connection.execute("SELECT * FROM scheduled_workouts WHERE id=? AND user_id=?", (scheduled_id, user_id)).fetchone()
            if not scheduled:
                raise NotFound("That scheduled workout was not found.")
            if scheduled["workout_id"] != workout_id or scheduled["scheduled_on"] != performed_on:
                raise BadRequest("The selected schedule must match the workout and date.")
            if scheduled["status"] != "planned":
                raise Conflict("This scheduled workout is already completed or skipped.")
        log_id = connection.execute("INSERT INTO workout_logs (user_id, workout_id, workout_name, performed_on, duration_seconds, status, estimated_calories, notes, scheduled_workout_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, workout_id, workout["name"], performed_on, round(minutes * 60), status, calories, notes, scheduled_id)).lastrowid
        connection.executemany("INSERT INTO exercise_logs (workout_log_id, exercise_id, exercise_name, muscle_group, set_number, reps, duration_seconds, load_kg) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(log_id, *entry) for entry in exercises])
        if scheduled_id is not None and status == "completed":
            connection.execute("UPDATE scheduled_workouts SET status='completed' WHERE id=? AND user_id=?", (scheduled_id, user_id))
    return log_id


NUTRIENTS = {
    "calories": "calories_per_serving",
    "protein_g": "protein_g_per_serving",
    "carbs_g": "carbs_g_per_serving",
    "fat_g": "fat_g_per_serving",
    "sodium_mg": "sodium_mg_per_serving",
}


def log_meal(connection, user_id, data):
    form = Form(data)
    meal_name = form.text("meal_name", "Meal name", 120)
    form.finish()
    consumed_on = iso_date(data.get("consumed_on"), "consumed_on", historical=True)
    items = data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise ValidationError({"items": "Add between 1 and 50 foods to your meal."})
    values = []
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError({"items": "Each food must contain nutrition details."})
        entry = Form(item)
        name = entry.text("food_name", "Food name", 120)
        serving = entry.text("serving_description", "Serving size", 120)
        servings = entry.number("servings", "servings", 0.01, 1000)
        calories = entry.number("calories_per_serving", "calories per serving", 0, 100000)
        nutrients = [optional_number(entry, column, column.replace("_", " "), 1000000) for column in list(NUTRIENTS.values())[1:]]
        if entry.errors:
            raise ValidationError(entry.errors)
        values.append((name, serving, servings, calories, *nutrients))
    with connection:
        log_id = connection.execute("INSERT INTO nutrition_logs (user_id, consumed_on, meal_name, source) VALUES (?, ?, ?, 'manual')", (user_id, consumed_on, meal_name)).lastrowid
        connection.executemany("INSERT INTO nutrition_items (nutrition_log_id, food_name, serving_description, servings, calories_per_serving, protein_g_per_serving, carbs_g_per_serving, fat_g_per_serving, sodium_mg_per_serving) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(log_id, *item) for item in values])
    return log_id


def delete_activity(connection, user_id, kind, log_id):
    # Table names come from this fixed mapping, never request text.
    table = {"workouts": "workout_logs", "meals": "nutrition_logs"}[kind]
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(f"SELECT * FROM {table} WHERE id=? AND user_id=?", (log_id, user_id)).fetchone()
        if row is None:
            raise NotFound("This entry was not found in your account.")
        connection.execute(f"DELETE FROM {table} WHERE id=? AND user_id=?", (log_id, user_id))
        if kind == "workouts" and row["scheduled_workout_id"]:
            completed = connection.execute("SELECT 1 FROM workout_logs WHERE scheduled_workout_id=? AND user_id=? AND status='completed'", (row["scheduled_workout_id"], user_id)).fetchone()
            connection.execute("UPDATE scheduled_workouts SET status=? WHERE id=? AND user_id=? AND status='completed'", ("completed" if completed else "planned", row["scheduled_workout_id"], user_id))
