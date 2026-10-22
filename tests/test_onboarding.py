"""Integration tests using real SQLite files and Flask's HTTP test client."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash

from fitworld import create_app
from fitworld.db import get_db, migrate


class FitworldTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE": str(Path(self.directory.name) / "test.sqlite3"),
        })
        with self.app.app_context():
            migrate()
        self.client = self.app.test_client()
        self.token = self.client.get("/api/session").json["csrf_token"]

    def tearDown(self):
        self.directory.cleanup()

    def write(self, path, data=None, method="POST", client=None, token=None):
        response = (client or self.client).open(
            f"/api/{path}", method=method, json=data if data is not None else {},
            headers={"X-CSRF-Token": token if token is not None else self.token},
        )
        if client is None and response.is_json and "csrf_token" in response.json:
            self.token = response.json["csrf_token"]
        return response

    def register(self, email="david@example.com", name="David"):
        return self.write("register", {"display_name": name, "email": email, "password": "a-long-test-password"})

    def baseline(self, **changes):
        data = {"age": 21, "weight": 70, "unit_system": "metric", "experience_level": "beginner", "current_workouts_per_week": 0}
        data.update(changes)
        return self.write("onboarding/profile", data, "PUT")

    def rhythm(self, **changes):
        data = {"primary_goal": "get_active", "training_location": "home", "target_days_per_week": 3, "session_minutes": 30}
        data.update(changes)
        return self.write("onboarding/preferences", data, "PUT")

    def test_page_and_assets_are_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create account", response.data)
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        with self.client.get("/static/onboarding.js") as asset:
            self.assertEqual(asset.status_code, 200)

    def test_default_local_signing_key_persists_with_private_permissions(self):
        instance = str(Path(self.directory.name) / "instance")
        first = create_app({"SECRET_KEY": None}, instance_path=instance)
        second = create_app({"SECRET_KEY": None}, instance_path=instance)
        self.assertEqual(first.config["SECRET_KEY"], second.config["SECRET_KEY"])
        self.assertEqual(len(first.config["SECRET_KEY"]), 64)
        self.assertEqual((Path(instance) / "session-secret").stat().st_mode & 0o777, 0o600)

    def test_registration_hashes_password_and_normalizes_email(self):
        response = self.register(" David@Example.com ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["user"]["email"], "david@example.com")
        self.assertIsNone(response.json["user"]["onboarding_completed_at"])
        self.assertNotIn("password_hash", response.json["user"])
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM users").fetchone()
            self.assertNotEqual(row["password_hash"], "a-long-test-password")
            self.assertTrue(check_password_hash(row["password_hash"], "a-long-test-password"))

    def test_duplicate_email_is_case_insensitive(self):
        self.register()
        self.write("logout")
        response = self.register("DAVID@EXAMPLE.COM")
        self.assertEqual(response.status_code, 409)
        self.assertIn("email", response.json["fields"])

    def test_invalid_account_fields_do_not_create_user(self):
        response = self.write("register", {"display_name": " ", "email": "bad", "password": "short"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(set(response.json["fields"]), {"display_name", "email", "password"})
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_login_logout_and_session_rotation(self):
        original_token = self.token
        self.register()
        self.assertNotEqual(original_token, self.token)
        self.assertEqual(self.write("onboarding/complete", token=original_token).status_code, 403)
        self.write("logout")
        self.assertIsNone(self.client.get("/api/session").json["user"])
        self.assertEqual(self.write("login", {"email": "david@example.com", "password": "wrong"}).status_code, 401)
        response = self.write("login", {"email": "david@example.com", "password": "a-long-test-password"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["user"]["display_name"], "David")

    def test_all_writes_require_csrf_token(self):
        response = self.client.post("/api/register", json={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.write("register", token="wrong").status_code, 403)

    def test_private_steps_require_authentication(self):
        self.assertEqual(self.baseline().status_code, 401)
        self.assertEqual(self.rhythm().status_code, 401)
        self.assertEqual(self.write("onboarding/complete").status_code, 401)

    def test_malformed_json_returns_json_error(self):
        for body in ([], None, "text", 42):
            with self.subTest(body=body):
                response = self.client.post("/api/register", json=body, headers={"X-CSRF-Token": self.token})
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.is_json)

    def test_completion_requires_both_steps_and_is_idempotent(self):
        self.register()
        self.assertEqual(self.write("onboarding/complete").status_code, 409)
        self.assertEqual(self.rhythm().status_code, 409)
        self.assertEqual(self.baseline().status_code, 200)
        self.assertEqual(self.write("onboarding/complete").status_code, 409)
        self.assertEqual(self.rhythm().status_code, 200)
        completed = self.write("onboarding/complete").json["user"]["onboarding_completed_at"]
        self.assertIsNotNone(completed)
        self.assertEqual(self.write("onboarding/complete").json["user"]["onboarding_completed_at"], completed)

    def test_draft_and_completed_profile_survive_new_login(self):
        self.register()
        self.baseline()
        self.write("logout")
        response = self.write("login", {"email": "david@example.com", "password": "a-long-test-password"})
        self.assertEqual(response.json["user"]["profile"]["age"], 21)
        self.assertIsNone(response.json["user"]["preferences"])
        self.rhythm()
        self.write("onboarding/complete")
        # A fresh application instance reads the same durable database.
        restarted = create_app(dict(self.app.config)).test_client()
        token = restarted.get("/api/session").json["csrf_token"]
        response = self.write("login", {"email": "david@example.com", "password": "a-long-test-password"}, client=restarted, token=token)
        self.assertEqual(response.json["user"]["preferences"]["target_days_per_week"], 3)
        self.assertIsNotNone(response.json["user"]["onboarding_completed_at"])

    def test_pounds_are_converted_and_daily_measurements_upsert(self):
        self.register()
        response = self.baseline(weight=154.3, unit_system="imperial")
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json["user"]["profile"]["weight_kg"], 69.989, places=3)
        self.baseline(weight=71)
        with self.app.app_context():
            rows = get_db().execute("SELECT * FROM body_measurements").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["weight_kg"], 71)

    def test_invalid_baseline_keeps_previous_data(self):
        self.register()
        self.baseline()
        for change in ({"age": 12}, {"age": 21.5}, {"age": True}, {"weight": "NaN"}, {"weight": "Infinity"}, {"weight": 0}, {"unit_system": []}, {"experience_level": "expert"}, {"current_workouts_per_week": 8}):
            with self.subTest(change=change):
                self.assertEqual(self.baseline(**change).status_code, 422)
        user = self.client.get("/api/session").json["user"]
        self.assertEqual(user["profile"]["age"], 21)
        self.assertEqual(user["profile"]["weight_kg"], 70)

    def test_invalid_preferences_are_rejected(self):
        self.register()
        self.baseline()
        for change in ({"primary_goal": "unknown"}, {"training_location": None}, {"target_days_per_week": 0}, {"target_days_per_week": 2.5}, {"session_minutes": 20}):
            with self.subTest(change=change):
                self.assertEqual(self.rhythm(**change).status_code, 422)
        self.assertIsNone(self.client.get("/api/session").json["user"]["preferences"])

    def test_request_user_id_cannot_modify_another_account(self):
        self.register()
        self.baseline()
        self.write("logout")
        second = self.register("soham@example.com", "Soham").json["user"]["id"]
        self.baseline(age=30, user_id=1)
        self.rhythm(user_id=1)
        with self.app.app_context():
            connection = get_db()
            self.assertEqual(connection.execute("SELECT age FROM user_profiles WHERE user_id=1").fetchone()[0], 21)
            self.assertEqual(connection.execute("SELECT age FROM user_profiles WHERE user_id=?", (second,)).fetchone()[0], 30)
            self.assertIsNone(connection.execute("SELECT * FROM workout_preferences WHERE user_id=1").fetchone())

    def test_sql_like_name_is_stored_as_data(self):
        name = "David'); DROP TABLE users;--"
        self.assertEqual(self.register(name=name).json["user"]["display_name"], name)
        self.assertEqual(self.client.get("/api/session").status_code, 200)

    def test_migrations_preserve_data_and_enforce_foreign_keys(self):
        self.register()
        with self.app.app_context():
            migrate()
            connection = get_db()
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO body_measurements (user_id, measured_on, weight_kg) VALUES (999, '2026-10-21', 70)")

    def test_schema_rejects_incomplete_completion_and_invalid_intensity(self):
        self.register()
        with self.app.app_context():
            connection = get_db()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE users SET onboarding_completed_at=CURRENT_TIMESTAMP WHERE id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO workouts (name, intensity, estimated_minutes, category) VALUES ('Impossible', 11, 30, 'strength')")

    def test_routines_reject_multiple_active_and_cross_user_schedules(self):
        self.register()
        self.write("logout")
        self.register("soham@example.com", "Soham")
        with self.app.app_context():
            connection = get_db()
            connection.execute("INSERT INTO routines (id, name, experience_level, duration_weeks) VALUES (1, 'Starter', 'beginner', 4)")
            connection.execute("INSERT INTO workouts (id, name, intensity, estimated_minutes, category) VALUES (1, 'Walk', 2, 15, 'cardio')")
            connection.execute("INSERT INTO user_routines (id, user_id, routine_id, starts_on) VALUES (1, 1, 1, '2026-10-21')")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO user_routines (user_id, routine_id, starts_on) VALUES (1, 1, '2026-10-22')")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO scheduled_workouts (user_id, user_routine_id, workout_id, scheduled_on) VALUES (2, 1, 1, '2026-10-21')")
            connection.execute("UPDATE user_routines SET status='replaced' WHERE id=1")
            connection.execute("INSERT INTO user_routines (user_id, routine_id, starts_on) VALUES (1, 1, '2026-10-22')")

    def test_user_deletion_cascades_private_history(self):
        self.register()
        self.baseline()
        self.rhythm()
        with self.app.app_context():
            connection = get_db()
            connection.execute("INSERT INTO workout_logs (user_id, workout_name, performed_on, duration_seconds, status) VALUES (1, 'Walk', '2026-10-21', 900, 'partial')")
            connection.execute("INSERT INTO exercise_logs (workout_log_id, exercise_name, muscle_group, set_number, duration_seconds) VALUES (1, 'Walk', 'legs', 1, 900)")
            connection.execute("INSERT INTO nutrition_logs (user_id, consumed_on, meal_name, source) VALUES (1, '2026-10-21', 'Lunch', 'manual')")
            connection.execute("INSERT INTO nutrition_items (nutrition_log_id, food_name, serving_description, servings, calories_per_serving) VALUES (1, 'Rice', 'cup', 2, 200)")
            connection.execute("INSERT INTO progress_photos (user_id, storage_key, taken_on) VALUES (1, 'private/example', '2026-10-21')")
            connection.execute("INSERT INTO goals (user_id, title, metric, target_value) VALUES (1, 'Three workouts', 'workouts', 3)")
            connection.execute("INSERT INTO milestones (user_id, title, achieved_on) VALUES (1, 'First workout', '2026-10-21')")
            connection.execute("DELETE FROM users WHERE id=1")
            for table in ("user_profiles", "workout_preferences", "body_measurements", "workout_logs", "exercise_logs", "nutrition_logs", "nutrition_items", "progress_photos", "goals", "milestones"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_nutrition_totals_use_servings_without_multiplying_workout_rows(self):
        with self.app.app_context():
            connection = get_db()
            connection.execute("INSERT INTO users (email, display_name, password_hash) VALUES ('test@example.com', 'Test', 'test-only')")
            connection.execute("INSERT INTO nutrition_logs (user_id, consumed_on, meal_name, source) VALUES (1, '2026-10-21', 'Lunch', 'manual')")
            connection.execute("INSERT INTO nutrition_items (nutrition_log_id, food_name, serving_description, servings, calories_per_serving, protein_g_per_serving) VALUES (1, 'Rice', 'cup', 2, 200, 4)")
            row = connection.execute("SELECT SUM(i.servings*i.calories_per_serving), SUM(i.servings*i.protein_g_per_serving) FROM nutrition_items i JOIN nutrition_logs n ON n.id=i.nutrition_log_id WHERE n.user_id=1 AND n.consumed_on='2026-10-21'").fetchone()
            self.assertEqual(tuple(row), (400, 8))


if __name__ == "__main__":
    unittest.main()
