"""Account and onboarding endpoints. Ownership comes only from the session."""

import secrets
import sqlite3
from functools import wraps

from flask import Blueprint, g, jsonify, request, session
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

from . import validation
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Send a JSON object.")
    return data


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def current_user():
    row = get_db().execute(
        "SELECT id, email, display_name, onboarding_completed_at FROM users WHERE id = ?",
        (session.get("user_id"),),
    ).fetchone()
    if row is None:
        return None
    user = dict(row)
    for key, table in (("profile", "user_profiles"), ("preferences", "workout_preferences")):
        record = get_db().execute(f"SELECT * FROM {table} WHERE user_id = ?", (row["id"],)).fetchone()
        user[key] = dict(record) if record else None
    return user


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        g.user = current_user()
        if not g.user:
            return jsonify(error="Sign in to continue."), 401
        return view(*args, **kwargs)

    return wrapped


@bp.errorhandler(validation.ValidationError)
def invalid_form(error):
    return jsonify(error="Check the highlighted fields.", fields=error.fields), 422


@bp.get("/session")
def get_session():
    return jsonify(user=current_user(), csrf_token=csrf_token())


def sign_in(user_id):
    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return {"user": current_user(), "csrf_token": csrf_token()}


@bp.post("/register")
def register():
    if session.get("user_id"):
        return jsonify(error="Sign out before creating another account."), 409
    email, password, name = validation.account(payload())
    connection = get_db()
    hashed = generate_password_hash(password)
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
                (email, name, hashed),
            )
    except sqlite3.IntegrityError:
        return jsonify(error="This email is already registered. Sign in to continue.", fields={"email": "This email is already registered."}), 409
    return jsonify(sign_in(cursor.lastrowid)), 201


@bp.post("/login")
def login():
    email, password, _ = validation.account(payload(), registering=False)
    row = get_db().execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify(error="Email or password is incorrect."), 401
    return jsonify(sign_in(row["id"]))


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(user=None, csrf_token=csrf_token())


@bp.put("/onboarding/profile")
@authenticated
def save_profile():
    age, weight, units, experience, current = validation.profile(payload())
    connection = get_db()
    with connection:
        connection.execute(
            """INSERT INTO user_profiles
               (user_id, age, weight_kg, unit_system, experience_level, current_workouts_per_week)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET age=excluded.age, weight_kg=excluded.weight_kg,
               unit_system=excluded.unit_system, experience_level=excluded.experience_level,
               current_workouts_per_week=excluded.current_workouts_per_week, updated_at=CURRENT_TIMESTAMP""",
            (g.user["id"], age, weight, units, experience, current),
        )
        connection.execute(
            """INSERT INTO body_measurements (user_id, measured_on, weight_kg)
               VALUES (?, date('now'), ?) ON CONFLICT(user_id, measured_on)
               DO UPDATE SET weight_kg=excluded.weight_kg""",
            (g.user["id"], weight),
        )
    return jsonify(user=current_user())


@bp.put("/onboarding/preferences")
@authenticated
def save_preferences():
    if not g.user["profile"]:
        return jsonify(error="Save your baseline before choosing preferences."), 409
    goal, location, days, minutes = validation.preferences(payload())
    connection = get_db()
    with connection:
        connection.execute(
            """INSERT INTO workout_preferences
               (user_id, primary_goal, training_location, target_days_per_week, session_minutes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET primary_goal=excluded.primary_goal,
               training_location=excluded.training_location, target_days_per_week=excluded.target_days_per_week,
               session_minutes=excluded.session_minutes, updated_at=CURRENT_TIMESTAMP""",
            (g.user["id"], goal, location, days, minutes),
        )
    return jsonify(user=current_user())


@bp.post("/onboarding/complete")
@authenticated
def complete_onboarding():
    if not g.user["profile"] or not g.user["preferences"]:
        return jsonify(error="Complete your baseline and preferences first."), 409
    connection = get_db()
    with connection:
        connection.execute(
            "UPDATE users SET onboarding_completed_at = COALESCE(onboarding_completed_at, CURRENT_TIMESTAMP) WHERE id = ?",
            (g.user["id"],),
        )
    return jsonify(user=current_user())
