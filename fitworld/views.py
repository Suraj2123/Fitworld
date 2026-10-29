"""Server-rendered navigation and access control for application pages."""

from flask import Blueprint, g, redirect, render_template

from .api import current_user

bp = Blueprint("pages", __name__)


@bp.before_request
def require_setup():
    g.user = current_user()
    if not g.user:
        return redirect("/?login=1")
    if not g.user["onboarding_completed_at"]:
        return redirect("/?setup=1")


@bp.get("/home")
def home():
    return render_template("home.html", page="home", title="Home")


@bp.get("/workouts")
def workouts():
    return render_template("workouts.html", page="workouts", title="Suggested Workouts")


@bp.get("/progress")
def progress():
    return render_template("progress.html", page="progress", title="Personal Progress")


@bp.get("/settings")
def settings():
    return render_template("settings.html", page="settings", title="Settings")
