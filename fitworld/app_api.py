"""Thin HTTP adapters for catalog, activity, and progress modules."""

from datetime import date, timedelta
from functools import wraps

from flask import Blueprint, g, jsonify, request

from . import activity, catalog, progress, reports
from .api import authenticated, invalid_form, payload
from .db import get_db
from .validation import ValidationError

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
    return jsonify(workouts=catalog.workouts(get_db(), g.user, request.args.get("q", "").strip()[:200]))


@bp.get("/workouts/<int:workout_id>")
@onboarded
def get_workout(workout_id):
    return jsonify(workout=catalog.workout_detail(get_db(), workout_id))


@bp.get("/routines")
@onboarded
def get_routines():
    return jsonify(routines=catalog.routines(get_db(), g.user, request.args.get("q", "").strip()[:200]), current=catalog.current_routine(get_db(), g.user["id"]))


@bp.post("/routines/<int:routine_id>/select")
@onboarded
def choose_routine(routine_id):
    starts_on = activity.iso_date(payload().get("starts_on"), "starts_on")
    return jsonify(current=catalog.select_routine(get_db(), g.user["id"], routine_id, starts_on))


@bp.get("/schedule")
@onboarded
def get_schedule():
    start = activity.iso_date(request.args.get("from", date.today().isoformat()), "from")
    end = activity.iso_date(request.args.get("to", (date.fromisoformat(start) + timedelta(days=6)).isoformat()), "to")
    if not 0 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 366:
        raise ValidationError({"to": "Choose a calendar range of at most one year, ending after its start."})
    return jsonify(schedule=catalog.schedule(get_db(), g.user["id"], start, end))


@bp.get("/activity")
@onboarded
def get_activity():
    selected = activity.iso_date(request.args.get("date", date.today().isoformat()))
    return jsonify(reports.daily_activity(get_db(), g.user["id"], selected))


@bp.get("/activity/recent")
@onboarded
def get_recent():
    rows = get_db().execute("SELECT id, workout_id, workout_name, performed_on, duration_seconds, status, estimated_calories FROM workout_logs WHERE user_id=? ORDER BY performed_on DESC, started_at DESC, id DESC LIMIT 8", (g.user["id"],)).fetchall()
    return jsonify(workouts=[dict(row) for row in rows])


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
    today = activity.iso_date(request.args.get("today", date.today().isoformat()), "today")
    month = request.args.get("month", today[:7])
    return jsonify(progress.monthly_progress(get_db(), g.user["id"], month, today))


@bp.post("/progress/measurements")
@onboarded
def save_measurement():
    return jsonify(measurement=progress.record_weight(get_db(), g.user["id"], payload())), 201
