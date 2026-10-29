"""Fitworld's local web application."""

import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.exceptions import HTTPException

from . import db


def create_app(test_config=None, *, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "fitworld.sqlite3"),
        SECRET_KEY=os.environ.get("FITWORLD_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FITWORLD_HTTPS") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        MAX_CONTENT_LENGTH=128 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        # Keep local sessions usable across restarts without committing a secret.
        secret_path = Path(app.instance_path) / "session-secret"
        try:
            with open(secret_path, "x", opener=lambda p, f: os.open(p, f, 0o600)) as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = secret_path.read_text().strip()

    db.init_app(app)
    from .api import bp

    app.register_blueprint(bp)
    from .app_api import bp as app_api
    from .views import bp as pages
    app.register_blueprint(app_api)
    app.register_blueprint(pages)

    @app.before_request
    def protect_writes():
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token")
            provided = request.headers.get("X-CSRF-Token", "")
            if not expected or not secrets.compare_digest(expected, provided):
                return jsonify(error="Your session changed. Reload the page and try again."), 403

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/") or session.get("user_id"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.get("/")
    def index():
        from .api import current_user
        user = current_user()
        if user and user["onboarding_completed_at"] and request.args.get("setup") != "1":
            return redirect("/home")
        return render_template("index.html")

    return app
