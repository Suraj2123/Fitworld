"""Validate and write private catalog definitions; callers supply the acting account.

Each operation owns its transaction. Shared catalog readers also enforce ownership,
so definitions have the same visibility when listed, inspected, or logged.
"""

import sqlite3

from werkzeug.exceptions import Conflict, NotFound

from .catalog import workout_detail
from .validation import Form, ValidationError


def create_exercise(connection, user_id, data):
    form = Form(data)
    name = form.text("name", "Exercise name", 100)
    description = form.text("description", "Description", 500)
    muscle = form.text("muscle_group", "Muscle group", 100)
    equipment = form.text("equipment", "Equipment", 100)
    form.finish()
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM exercises WHERE user_id=? AND name=? COLLATE NOCASE", (user_id, name)
        ).fetchone():
            raise ValidationError({"name": "You already have an exercise with this name."})
        exercise_id = connection.execute(
            "INSERT INTO exercises (name, description, muscle_group, equipment, user_id) VALUES (?, ?, ?, ?, ?)",
            (name, description, muscle, equipment, user_id),
        ).lastrowid
        exercise = dict(
            connection.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
        )
    return exercise


def _prescriptions(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        raise ValidationError({"exercises": "Add between 1 and 50 exercises."})
    rows = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValidationError({"exercises": "Each prescription must contain exercise details."})
        form = Form({"suggested_sets": 1, **item})
        exercise_id = form.number("exercise_id", "exercise", 1, 2**53, integer=True)
        sets = form.number("suggested_sets", "suggested sets", 1, 20, integer=True)
        reps = (
            form.number("suggested_reps", "suggested reps", 1, 10000, integer=True)
            if item.get("suggested_reps") not in (None, "")
            else None
        )
        seconds = (
            form.number("suggested_seconds", "suggested seconds", 1, 86400, integer=True)
            if item.get("suggested_seconds") not in (None, "")
            else None
        )
        if reps is None and seconds is None:
            form.errors["prescription"] = "Provide suggested reps or a duration for every exercise."
        if form.errors:
            raise ValidationError({"exercises": " ".join(form.errors.values())})
        if exercise_id in seen:
            raise ValidationError({"exercises": "Add each exercise once and adjust its set count."})
        seen.add(exercise_id)
        rows.append((exercise_id, sets, reps, seconds))
    if sum(row[1] for row in rows) > 200:
        raise ValidationError({"exercises": "Keep the workout within 200 total sets."})
    return rows


def create_workout(connection, user_id, data):
    form = Form(data)
    name = form.text("name", "Workout name", 100)
    description = form.text("description", "Description", 500)
    intensity = form.number("intensity", "intensity", 1, 10, integer=True)
    minutes = form.number("estimated_minutes", "session length", 15, 90, integer=True)
    category = form.choice(
        "category", {"strength", "cardio", "mobility", "recovery", "mixed"}, "a category"
    )
    form.finish()
    prescriptions = _prescriptions(data.get("exercises"))
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM workouts WHERE user_id=? AND name=?", (user_id, name)
        ).fetchone():
            raise ValidationError({"name": "You already have a workout with this name."})
        for exercise_id, *_ in prescriptions:
            if not connection.execute(
                "SELECT 1 FROM exercises WHERE id=? AND (user_id IS NULL OR user_id=?)",
                (exercise_id, user_id),
            ).fetchone():
                raise ValidationError(
                    {"exercises": "Choose shared exercises or your own exercises."}
                )
        workout_id = connection.execute(
            "INSERT INTO workouts (name, description, intensity, estimated_minutes, category, image_path, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                description,
                intensity,
                minutes,
                category,
                f"/static/art/{category}.svg",
                user_id,
            ),
        ).lastrowid
        connection.executemany(
            "INSERT INTO workout_exercises (workout_id, exercise_id, position, suggested_sets, suggested_reps, suggested_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (workout_id, exercise_id, position, sets, reps, seconds)
                for position, (exercise_id, sets, reps, seconds) in enumerate(prescriptions, 1)
            ],
        )
        workout = workout_detail(connection, workout_id, user_id)
    return workout


def delete_workout(connection, user_id, workout_id):
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if not connection.execute(
            "SELECT 1 FROM workouts WHERE id=? AND user_id=?", (workout_id, user_id)
        ).fetchone():
            raise NotFound("This custom workout was not found in your account.")
        try:
            connection.execute(
                "DELETE FROM workouts WHERE id=? AND user_id=?", (workout_id, user_id)
            )
        except sqlite3.IntegrityError:
            raise Conflict(
                "This workout is part of a routine or schedule and cannot be removed."
            ) from None
