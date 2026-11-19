"""Thin HTTP adapters for catalog, activity, and progress modules."""

from datetime import date, timedelta
from functools import wraps

from flask import Blueprint, g, jsonify, request

from . import activity, catalog, custom_catalog, measurements, progress, reports, weekly_goals
from .api import authenticated, invalid_form, payload
from .db import get_db
from .validation import ValidationError, iso_date

bp = Blueprint("app_api", __name__, url_prefix="/api")
bp.register_error_handler(ValidationError, invalid_form)


def onboarded(view):
    @wraps(view)
    @authenticated
    def wrapped(*args, **kwargs):
        if not g.user["onboarding_completed_at"]:
            return jsonify(error="Finish your starting point first.", next="/?setup=1"), 409
        return view(*args, **kwargs)

    return wrapped


@bp.get("/workouts")
@onboarded
def get_workouts():
    return jsonify(
        workouts=catalog.workouts(get_db(), g.user, request.args.get("q", "").strip()[:200])
    )


@bp.get("/exercises")
@onboarded
def get_exercises():
    return jsonify(
        exercises=catalog.exercises(get_db(), g.user["id"], request.args.get("q", "").strip()[:200])
    )


@bp.get("/workouts/<int:workout_id>")
@onboarded
def get_workout(workout_id):
    return jsonify(workout=catalog.workout_detail(get_db(), workout_id, g.user["id"]))


@bp.get("/routines")
@onboarded
def get_routines():
    today = iso_date(request.args.get("today", date.today().isoformat()), "today")
    return jsonify(
        routines=catalog.routines(get_db(), g.user, request.args.get("q", "").strip()[:200]),
        current=catalog.current_routine(get_db(), g.user["id"], as_of=today),
    )


@bp.post("/routines/<int:routine_id>/select")
@onboarded
def choose_routine(routine_id):
    starts_on = iso_date(payload().get("starts_on"), "starts_on")
    return jsonify(current=catalog.select_routine(get_db(), g.user["id"], routine_id, starts_on))


@bp.get("/schedule")
@onboarded
def get_schedule():
    start = iso_date(request.args.get("from", date.today().isoformat()), "from")
    end = iso_date(
        request.args.get("to", (date.fromisoformat(start) + timedelta(days=6)).isoformat()), "to"
    )
    if not 0 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 366:
        raise ValidationError(
            {"to": "Choose a calendar range of at most one year, ending after its start."}
        )
    return jsonify(schedule=catalog.schedule(get_db(), g.user["id"], start, end))


@bp.get("/activity")
@onboarded
def get_activity():
    selected = iso_date(request.args.get("date", date.today().isoformat()))
    return jsonify(reports.daily_activity(get_db(), g.user["id"], selected))


@bp.get("/activity/recent")
@onboarded
def get_recent():
    return jsonify(workouts=reports.recent_activity(get_db(), g.user["id"]))


@bp.get("/activity/workouts")
@onboarded
def get_workout_history():
    pagination = {}
    for key, default, maximum in (("page", "1", 2147483647), ("per_page", "20", 100)):
        value = request.args.get(key, default)
        if (
            not value.isascii()
            or not value.isdigit()
            or len(value) > 10
            or not 1 <= int(value) <= maximum
        ):
            raise ValidationError({key: f"Choose a whole number between 1 and {maximum}."})
        pagination[key] = int(value)
    return jsonify(reports.workout_history(get_db(), g.user["id"], **pagination))


@bp.post("/activity/workouts")
@onboarded
def save_workout():
    log_id = activity.log_workout(get_db(), g.user["id"], payload())
    return jsonify(id=log_id), 201


@bp.post("/activity/meals")
@onboarded
def save_meal():
    log_id = activity.log_meal(get_db(), g.user["id"], payload())
    return jsonify(id=log_id), 201


@bp.delete("/activity/workouts/<int:log_id>")
@onboarded
def remove_workout(log_id):
    activity.delete_activity(get_db(), g.user["id"], "workouts", log_id)
    return jsonify(deleted=True)


@bp.delete("/activity/meals/<int:log_id>")
@onboarded
def remove_meal(log_id):
    activity.delete_activity(get_db(), g.user["id"], "meals", log_id)
    return jsonify(deleted=True)


@bp.get("/progress")
@onboarded
def get_progress():
    today = iso_date(request.args.get("today", date.today().isoformat()), "today")
    month = request.args.get("month", today[:7])
    return jsonify(progress.monthly_progress(get_db(), g.user["id"], month, today))


@bp.post("/progress/measurements")
@onboarded
def save_measurement():
    return jsonify(measurement=measurements.record_weight(get_db(), g.user["id"], payload())), 201


@bp.get("/progress/weekly")
@onboarded
def get_weekly_progress():
    today = iso_date(request.args.get("today", date.today().isoformat()), "today")
    selected = iso_date(request.args.get("date", today))
    return jsonify(weekly_goals.weekly_progress(get_db(), g.user["id"], selected, today))


@bp.post("/exercises")
@onboarded
def create_exercise():
    return jsonify(exercise=custom_catalog.create_exercise(get_db(), g.user["id"], payload())), 201


@bp.post("/workouts/custom")
@onboarded
def create_custom_workout():
    return jsonify(workout=custom_catalog.create_workout(get_db(), g.user["id"], payload())), 201


@bp.delete("/workouts/<int:workout_id>")
@onboarded
def remove_custom_workout(workout_id):
    custom_catalog.delete_workout(get_db(), g.user["id"], workout_id)
    return jsonify(deleted=True)


@bp.put("/activity/meals/<int:log_id>")
@onboarded
def edit_meal(log_id):
    return jsonify(id=activity.log_meal(get_db(), g.user["id"], payload(), log_id))


@bp.get("/foods/recent")
@onboarded
def get_recent_foods():
    return jsonify(foods=reports.recent_foods(get_db(), g.user["id"]))


@bp.put("/activity/workouts/<int:log_id>")
@onboarded
def edit_workout(log_id):
    return jsonify(id=activity.edit_manual_workout(get_db(), g.user["id"], log_id, payload()))
