"""Shared catalog and routine enrollment; starter data never includes user history."""

from datetime import date, timedelta

from werkzeug.exceptions import BadRequest, NotFound

GOAL_CATEGORIES = {"get_active": "mixed", "build_strength": "strength", "improve_endurance": "cardio", "improve_mobility": "mobility"}


STARTERS = [
    # name, category, intensity, minutes, description, exercises (name, muscle, equipment, sets, reps, seconds)
    ("Bodyweight foundations", "strength", 3, 20, "A simple introduction to full-body movement, with time to find your form.", [
        ("Bodyweight squat", "Legs", "none", 2, 8, None), ("Wall push-up", "Chest", "none", 2, 8, None), ("Standing calf raise", "Calves", "none", 2, 10, None)]),
    ("Everyday strength", "strength", 5, 30, "Build on the basics with a balanced session for your upper and lower body.", [
        ("Bodyweight squat", "Legs", "none", 3, 10, None), ("Push-up", "Chest", "none", 3, 8, None), ("Glute bridge", "Glutes", "none", 3, 10, None)]),
    ("Gym strength", "strength", 6, 45, "A straightforward gym session with space to record your own loads and reps.", [
        ("Goblet squat", "Legs", "dumbbell", 3, 8, None), ("Dumbbell row", "Back", "dumbbell", 3, 10, None), ("Dumbbell press", "Shoulders", "dumbbell", 3, 8, None)]),
    ("Fresh-air walk", "cardio", 2, 15, "Step outside for an easy-paced walk and a change of scenery.", [
        ("Walking", "Legs", "outdoors", 1, None, 900)]),
    ("Steady cardio", "cardio", 5, 30, "A steady session to build consistency at a pace you choose.", [
        ("March in place", "Legs", "none", 2, None, 300), ("Step touch", "Full body", "none", 2, None, 300)]),
    ("Full-body circuit", "mixed", 8, 30, "A higher-intensity mix of familiar movements. Adjust the pace and rest to suit you.", [
        ("Bodyweight squat", "Legs", "none", 3, 12, None), ("Push-up", "Chest", "none", 3, 10, None), ("March in place", "Full body", "none", 3, None, 60)]),
    ("Mobility flow", "mobility", 2, 15, "Make a little room for comfortable movement through your usual range.", [
        ("Shoulder circles", "Shoulders", "none", 2, None, 30), ("Cat-cow", "Back", "none", 2, None, 45), ("Ankle circles", "Calves", "none", 2, None, 30)]),
    ("Recovery reset", "recovery", 1, 15, "An unhurried session for a lighter day. Keep the movements easy and comfortable.", [
        ("Shoulder circles", "Shoulders", "none", 1, None, 30), ("Cat-cow", "Back", "none", 1, None, 45), ("Easy breathing", "Recovery", "none", 1, None, 120)]),
]

ROUTINES = [
    ("A little more movement", "beginner", "An approachable four-week rhythm with two sessions each week.", [(1, "Bodyweight foundations"), (4, "Mobility flow")]),
    ("Build your foundation", "beginner", "Three sessions a week, with a mix of strength and easy movement.", [(1, "Bodyweight foundations"), (3, "Steady cardio"), (5, "Recovery reset")]),
    ("Strength in your week", "intermediate", "Three gym and recovery sessions each week, with space between strength days.", [(1, "Gym strength"), (3, "Mobility flow"), (5, "Gym strength")]),
    ("Keep the momentum", "advanced", "A four-day mix of strength, cardio, and recovery over four weeks.", [(1, "Gym strength"), (2, "Steady cardio"), (4, "Full-body circuit"), (6, "Recovery reset")]),
]


def seed_catalog(connection):
    """Insert missing starter definitions; preserve existing catalog edits and all user data."""
    with connection:
        for name, category, intensity, minutes, description, exercises in STARTERS:
            created = connection.execute(
                "INSERT INTO workouts (name, category, intensity, estimated_minutes, description, image_path) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(name) DO NOTHING",
                (name, category, intensity, minutes, description, f"/static/art/{category}.svg"),
            ).rowcount
            workout_id = connection.execute("SELECT id FROM workouts WHERE name=?", (name,)).fetchone()[0]
            for position, (exercise, muscle, equipment, sets, reps, seconds) in enumerate(exercises, 1):
                connection.execute("INSERT INTO exercises (name, muscle_group, equipment) VALUES (?, ?, ?) ON CONFLICT(name) DO NOTHING", (exercise, muscle, equipment))
                if created:
                    exercise_id = connection.execute("SELECT id FROM exercises WHERE name=?", (exercise,)).fetchone()[0]
                    connection.execute("INSERT INTO workout_exercises (workout_id, exercise_id, position, suggested_sets, suggested_reps, suggested_seconds) VALUES (?, ?, ?, ?, ?, ?)", (workout_id, exercise_id, position, sets, reps, seconds))
        for name, level, description, schedule in ROUTINES:
            created = connection.execute("INSERT INTO routines (name, description, experience_level, duration_weeks) VALUES (?, ?, ?, 4) ON CONFLICT(name) DO NOTHING", (name, description, level)).rowcount
            if created:
                routine_id = connection.execute("SELECT id FROM routines WHERE name=?", (name,)).fetchone()[0]
                for week in range(1, 5):
                    for day, workout in schedule:
                        workout_id = connection.execute("SELECT id FROM workouts WHERE name=?", (workout,)).fetchone()[0]
                        connection.execute("INSERT INTO routine_workouts (routine_id, workout_id, week_number, day_of_week) VALUES (?, ?, ?, ?)", (routine_id, workout_id, week, day))


def workouts(connection, user, query=""):
    rows = [dict(row) for row in connection.execute("SELECT * FROM workouts ORDER BY name")]
    prescriptions = connection.execute("SELECT we.*, e.name, e.muscle_group, e.equipment FROM workout_exercises we JOIN exercises e ON e.id=we.exercise_id ORDER BY we.workout_id, we.position").fetchall()
    by_workout = {}
    for row in prescriptions:
        by_workout.setdefault(row["workout_id"], []).append(dict(row))
    active_ids = {row[0] for row in connection.execute("SELECT rw.workout_id FROM user_routines ur JOIN routine_workouts rw ON rw.routine_id=ur.routine_id WHERE ur.user_id=? AND ur.status='active'", (user["id"],))}
    profile, preferences = user.get("profile") or {}, user.get("preferences") or {}
    preferred = GOAL_CATEGORIES.get(preferences.get("primary_goal"))
    target_intensity = {"beginner": 3, "intermediate": 5, "advanced": 7}.get(profile.get("experience_level"), 3)
    result = []
    for workout in rows:
        workout["exercises"] = by_workout.get(workout["id"], [])
        workout["muscle_groups"] = sorted({exercise["muscle_group"] for exercise in workout["exercises"]})
        workout["equipment"] = sorted({exercise["equipment"] for exercise in workout["exercises"] if exercise["equipment"] != "none"})
        workout["in_routine"] = workout["id"] in active_ids
        searchable = " ".join([workout["name"], workout["description"], *(exercise["name"] for exercise in workout["exercises"])]).lower()
        if query.lower() not in searchable:
            continue
        score = (100 if workout["in_routine"] else 0) + (20 if workout["category"] == preferred else 0) - abs(workout["intensity"] - target_intensity) * 3
        score -= max(0, workout["estimated_minutes"] - preferences.get("session_minutes", 30))
        if preferences.get("training_location") == "home" and workout["equipment"]:
            score -= 30
        if preferences.get("training_location") == "outdoors" and "outdoors" in workout["equipment"]:
            score += 20
        workout["recommendation_score"] = score
        result.append(workout)
    return sorted(result, key=lambda workout: (-workout["recommendation_score"], workout["name"]))


def workout_detail(connection, workout_id):
    # Catalog reading is shared by the detail page and the log validator.
    for workout in workouts(connection, {"id": -1}):
        if workout["id"] == workout_id:
            return workout
    raise NotFound("This workout is no longer in the catalog.")


def routines(connection, user, query=""):
    result = []
    preferences = user.get("preferences") or {}
    preferred = GOAL_CATEGORIES.get(preferences.get("primary_goal"))
    equipment = {}
    for item in connection.execute("SELECT DISTINCT rw.routine_id, e.equipment FROM routine_workouts rw JOIN workout_exercises we ON we.workout_id=rw.workout_id JOIN exercises e ON e.id=we.exercise_id WHERE e.equipment!='none'"):
        equipment.setdefault(item["routine_id"], set()).add(item["equipment"])
    for row in connection.execute("SELECT * FROM routines ORDER BY name"):
        routine = dict(row)
        routine["schedule"] = [dict(item) for item in connection.execute("SELECT rw.*, w.name, w.estimated_minutes, w.category FROM routine_workouts rw JOIN workouts w ON w.id=rw.workout_id WHERE rw.routine_id=? ORDER BY rw.week_number, rw.day_of_week, rw.position", (row["id"],))]
        searchable = " ".join([routine["name"], routine["description"], *(item["name"] for item in routine["schedule"])]).lower()
        if query.lower() in searchable:
            routine["matches_level"] = routine["experience_level"] == (user.get("profile") or {}).get("experience_level")
            first_week = [item for item in routine["schedule"] if item["week_number"] == 1]
            routine["equipment"] = sorted(equipment.get(routine["id"], set()))
            score = (30 if routine["matches_level"] else 0) + 10 * sum(item["category"] == preferred for item in first_week)
            score -= 5 * abs(len(first_week) - preferences.get("target_days_per_week", 3))
            if preferences.get("training_location") == "home" and routine["equipment"]:
                score -= 30
            routine["recommendation_score"] = score
            result.append(routine)
    return sorted(result, key=lambda routine: (-routine["recommendation_score"], routine["name"]))


def current_routine(connection, user_id):
    row = connection.execute("SELECT ur.*, r.name, r.description, r.duration_weeks FROM user_routines ur JOIN routines r ON r.id=ur.routine_id WHERE ur.user_id=? AND ur.status='active'", (user_id,)).fetchone()
    return dict(row) if row else None


def select_routine(connection, user_id, routine_id, starts_on):
    routine = connection.execute("SELECT * FROM routines WHERE id=?", (routine_id,)).fetchone()
    if routine is None:
        raise NotFound("This routine is no longer in the catalog.")
    prescriptions = connection.execute("SELECT * FROM routine_workouts WHERE routine_id=? ORDER BY week_number, day_of_week, position", (routine_id,)).fetchall()
    if not prescriptions or any(row["week_number"] > routine["duration_weeks"] for row in prescriptions):
        raise BadRequest("This routine needs a valid schedule before it can be selected.")
    start = date.fromisoformat(starts_on)
    monday = start - timedelta(days=start.weekday())
    with connection:
        # Serialize replacement with other writers before reading the current plan.
        connection.execute("BEGIN IMMEDIATE")
        active = current_routine(connection, user_id)
        if active and active["routine_id"] == routine_id and active["starts_on"] == starts_on:
            return active
        connection.execute("UPDATE scheduled_workouts SET status='skipped' WHERE user_id=? AND status='planned' AND scheduled_on>=? AND user_routine_id IN (SELECT id FROM user_routines WHERE user_id=? AND status='active')", (user_id, starts_on, user_id))
        connection.execute("UPDATE user_routines SET status='replaced' WHERE user_id=? AND status='active'", (user_id,))
        enrollment = connection.execute("INSERT INTO user_routines (user_id, routine_id, starts_on) VALUES (?, ?, ?)", (user_id, routine_id, starts_on)).lastrowid
        for row in prescriptions:
            scheduled = monday + timedelta(weeks=row["week_number"] - 1, days=row["day_of_week"] - 1)
            if scheduled >= start:
                connection.execute("INSERT INTO scheduled_workouts (user_id, user_routine_id, workout_id, scheduled_on) VALUES (?, ?, ?, ?)", (user_id, enrollment, row["workout_id"], scheduled.isoformat()))
    return current_routine(connection, user_id)


def schedule(connection, user_id, starts_on, ends_on):
    return [dict(row) for row in connection.execute("SELECT s.*, w.name, w.estimated_minutes, w.category FROM scheduled_workouts s JOIN workouts w ON w.id=s.workout_id WHERE s.user_id=? AND s.scheduled_on BETWEEN ? AND ? ORDER BY s.scheduled_on, s.id", (user_id, starts_on, ends_on))]
