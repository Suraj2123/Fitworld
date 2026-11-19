"""Private definitions use the same ownership rules in discovery, details and logging."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import AppCase

from fitworld import create_app
from fitworld.catalog import seed_catalog
from fitworld.db import get_db, migrate


class CustomCatalogTests(AppCase):
    def exercise(self, client=None, **changes):
        data = {
            "name": "Private hinge",
            "description": "A controlled movement.",
            "muscle_group": "Legs",
            "equipment": "none",
        }
        return self.write("exercises", {**data, **changes}, client=client)

    def custom(self, exercise_id=None, client=None, **changes):
        data = {
            "name": "Private workout",
            "description": "A personal session.",
            "intensity": 3,
            "estimated_minutes": 20,
            "category": "strength",
            "exercises": [
                {
                    "exercise_id": exercise_id or self.workout["exercises"][0]["exercise_id"],
                    "suggested_sets": 2,
                    "suggested_reps": 8,
                }
            ],
        }
        return self.write("workouts/custom", {**data, **changes}, client=client)

    def test_creation_returns_serializable_definitions_and_can_be_logged(self):
        exercise = self.exercise()
        self.assertEqual(exercise.status_code, 201)
        exercise_id = exercise.json["exercise"]["id"]
        response = self.custom(exercise_id)
        self.assertEqual(response.status_code, 201)
        workout = response.json["workout"]
        self.assertEqual(workout["exercises"][0]["name"], "Private hinge")
        self.assertEqual(workout["image_path"], "/static/art/strength.svg")
        self.assertEqual(self.client.get(f"/api/workouts/{workout['id']}").status_code, 200)
        self.assertEqual(self.log(workout_id=workout["id"]).status_code, 201)
        self.assertEqual(self.day_data()["workouts"][0]["muscle_groups"], ["Legs"])

    def test_other_accounts_cannot_discover_inspect_log_delete_or_attach_private_definitions(self):
        exercise_id = self.exercise().json["exercise"]["id"]
        workout_id = self.custom(exercise_id).json["workout"]["id"]
        other = self.app.test_client()
        self.create_account(other, "private-other@example.com")
        self.assertEqual(other.get("/api/workouts?q=Private").json["workouts"], [])
        self.assertEqual(other.get("/api/exercises?q=Private").json["exercises"], [])
        self.assertEqual(other.get(f"/api/workouts/{workout_id}").status_code, 404)
        response = self.write(
            "activity/workouts",
            {
                "workout_id": workout_id,
                "performed_on": self.day,
                "duration_minutes": 20,
                "status": "completed",
            },
            client=other,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.write(f"workouts/{workout_id}", method="DELETE", client=other).status_code, 404
        )
        self.assertEqual(self.custom(exercise_id, client=other).status_code, 422)
        self.assertEqual(self.client.get(f"/api/workouts/{workout_id}").status_code, 200)

    def test_names_are_scoped_to_owner_and_shared_catalog_stays_unchanged(self):
        self.assertEqual(self.exercise().status_code, 201)
        self.assertEqual(self.exercise(name="PRIVATE HINGE").status_code, 422)
        self.assertEqual(self.custom().status_code, 201)
        self.assertEqual(self.custom().status_code, 422)
        other = self.app.test_client()
        self.create_account(other, "same-name@example.com")
        self.assertEqual(self.exercise(client=other).status_code, 201)
        self.assertEqual(self.custom(client=other).status_code, 201)
        shared_name = self.workout["name"]
        self.assertEqual(self.custom(name=shared_name).status_code, 201)
        shared_exercise = self.workout["exercises"][0]["name"]
        self.assertEqual(self.exercise(name=shared_exercise).status_code, 201)
        with self.app.app_context():
            connection = get_db()
            seed_catalog(connection)
            seed_catalog(connection)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM workouts WHERE name=? AND user_id IS NULL", (shared_name,)
                ).fetchone()[0],
                1,
            )
        self.assertEqual(
            self.client.get(f"/api/workouts/{self.workout['id']}").json["workout"]["description"],
            self.workout["description"],
        )

    def test_prescriptions_reject_invalid_shapes_and_values_without_creating_parent(self):
        valid = {"exercise_id": self.workout["exercises"][0]["exercise_id"], "suggested_reps": 8}
        cases = [None, [], [None], ["invalid"], [valid, valid], [valid] * 51]
        cases += [
            [{**valid, **change}]
            for change in (
                {"exercise_id": True},
                {"exercise_id": 999999},
                {"suggested_sets": 0},
                {"suggested_sets": 1.5},
                {"suggested_sets": 21},
                {"suggested_reps": -1},
                {"suggested_reps": 2.5},
                {"suggested_reps": None},
                {"suggested_seconds": "Infinity"},
            )
        ]
        definitions = self.client.get("/api/exercises").json["exercises"][:11]
        cases.append(
            [
                {**valid, "exercise_id": exercise["id"], "suggested_sets": 20}
                for exercise in definitions
            ]
        )
        for prescriptions in cases:
            with self.subTest(prescriptions=prescriptions):
                response = self.custom(exercises=prescriptions)
                self.assertEqual(response.status_code, 422)
                self.assertIn("exercises", response.json["fields"])
                self.assertEqual(self.client.get("/api/workouts?q=Private").json["workouts"], [])

    def test_timed_prescription_defaults_to_one_set_and_metadata_is_validated(self):
        exercise_id = self.workout["exercises"][0]["exercise_id"]
        response = self.custom(exercises=[{"exercise_id": exercise_id, "suggested_seconds": 30}])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["workout"]["exercises"][0]["suggested_sets"], 1)
        for change in (
            {"intensity": True},
            {"category": "unknown"},
            {"name": " "},
            {"estimated_minutes": 91},
        ):
            with self.subTest(change=change):
                self.assertEqual(self.custom(**change).status_code, 422)

    def test_owner_is_session_not_body_and_new_writes_require_csrf_and_onboarding(self):
        response = self.exercise(user_id=999999)
        self.assertEqual(response.status_code, 201)
        actual_owner = self.client.get("/api/session").json["user"]["id"]
        self.assertEqual(response.json["exercise"]["user_id"], actual_owner)
        anon = self.app.test_client()
        self.assertEqual(self.exercise(client=anon).status_code, 401)
        self.write(
            "register",
            {
                "display_name": "Pending",
                "email": "pending-custom@example.com",
                "password": "long-test-password",
            },
            client=anon,
        )
        self.assertEqual(self.exercise(client=anon).status_code, 409)
        for path, method in (
            ("/api/exercises", "POST"),
            ("/api/workouts/custom", "POST"),
            ("/api/workouts/1", "DELETE"),
        ):
            self.assertEqual(self.client.open(path, method=method, json={}).status_code, 403)

    def test_deleting_definition_preserves_recorded_history_and_exercise_snapshots(self):
        exercise_id = self.exercise().json["exercise"]["id"]
        workout_id = self.custom(exercise_id).json["workout"]["id"]
        self.log(
            workout_id=workout_id,
            exercises=[{"exercise_id": exercise_id, "set_number": 1, "reps": 8, "load_kg": 12}],
        )
        self.assertEqual(self.write(f"workouts/{workout_id}", method="DELETE").status_code, 200)
        logged = self.day_data()["workouts"][0]
        self.assertIsNone(logged["workout_id"])
        self.assertEqual(logged["workout_name"], "Private workout")
        self.assertEqual(logged["muscle_groups"], ["Legs"])
        self.assertEqual(logged["exercises"][0]["load_kg"], 12)
        self.assertEqual(
            self.write(f"workouts/{self.workout['id']}", method="DELETE").status_code, 404
        )

    def test_account_deletion_cascades_private_catalog_and_logs(self):
        exercise_id = self.exercise().json["exercise"]["id"]
        workout_id = self.custom(exercise_id).json["workout"]["id"]
        self.log(workout_id=workout_id)
        with self.app.app_context():
            connection = get_db()
            connection.execute("DELETE FROM users")
            connection.commit()
            self.assertIsNone(
                connection.execute("SELECT 1 FROM exercises WHERE id=?", (exercise_id,)).fetchone()
            )
            self.assertIsNone(
                connection.execute("SELECT 1 FROM workouts WHERE id=?", (workout_id,)).fetchone()
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM workout_logs").fetchone()[0], 0
            )
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_failed_parent_rebuild_rolls_back_schema_data_and_version_and_restores_foreign_keys(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory, self.app.app_context():
            broken = Path(directory) / "999_broken.sql"
            broken.write_text(
                "-- fitworld: rebuild-parent-tables\nCREATE TABLE rollback_probe (id INTEGER);\nINSERT INTO workout_exercises (workout_id, exercise_id, position, suggested_reps) VALUES (999999, 999999, 1, 8);\n"
            )
            connection = get_db()
            before = connection.execute("SELECT COUNT(*) FROM workout_exercises").fetchone()[0]
            with (
                patch("fitworld.db.Path.glob", return_value=[broken]),
                self.assertRaises(sqlite3.IntegrityError),
            ):
                migrate()
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM workout_exercises").fetchone()[0], before
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=?", (broken.name,)
                ).fetchone()
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='rollback_probe'"
                ).fetchone()
            )


class PrivateCatalogUpgradeTests(unittest.TestCase):
    def test_populated_version_006_upgrade_preserves_ids_references_and_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(
                {
                    "TESTING": True,
                    "SECRET_KEY": "upgrade-test",
                    "DATABASE": str(Path(directory) / "old.sqlite3"),
                }
            )
            with app.app_context():
                connection = get_db()
                connection.execute(
                    "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                migrations = Path(__file__).resolve().parents[1] / "fitworld" / "migrations"
                for path in sorted(migrations.glob("*.sql")):
                    if path.name.startswith("007_"):
                        break
                    connection.executescript(path.read_text())
                    connection.execute(
                        "INSERT INTO schema_migrations (version) VALUES (?)", (path.name,)
                    )
                    connection.commit()
                connection.execute(
                    "INSERT INTO users (id,email,display_name,password_hash) VALUES (1000,'old@example.com','Old','existing-hash')"
                )
                connection.execute(
                    "INSERT INTO exercises (id,name,muscle_group,user_id) VALUES (1000,'Private original','Legs',1000)"
                )
                connection.execute(
                    "INSERT INTO workouts (id,name,intensity,estimated_minutes,category,user_id) VALUES (1000,'Bodyweight foundations',3,20,'strength',1000)"
                )
                connection.execute(
                    "INSERT INTO workout_exercises (workout_id,exercise_id,position,suggested_reps) VALUES (1000,1000,1,8)"
                )
                connection.execute(
                    "INSERT INTO scheduled_workouts (id,user_id,workout_id,scheduled_on) VALUES (1000,1000,1000,'2026-01-05')"
                )
                connection.execute(
                    "INSERT INTO workout_logs (id,user_id,workout_id,workout_name,performed_on,duration_seconds,status,scheduled_workout_id,muscle_groups_snapshot) VALUES (1000,1000,1000,'Historical name','2026-01-05',600,'completed',1000,?)",
                    ('{"groups":["Legs"],"source":"recorded_sets"}',),
                )
                connection.execute(
                    "INSERT INTO exercise_logs (workout_log_id,exercise_id,exercise_name,muscle_group,set_number,reps) VALUES (1000,1000,'Historical move','Legs',1,8)"
                )
                connection.commit()
                migrate()
                seed_catalog(connection)
                migrate()
                seed_catalog(connection)
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                logged = connection.execute("SELECT * FROM workout_logs WHERE id=1000").fetchone()
                self.assertEqual(
                    (logged["workout_id"], logged["scheduled_workout_id"], logged["workout_name"]),
                    (1000, 1000, "Historical name"),
                )
                self.assertIn('"Legs"', logged["muscle_groups_snapshot"])
                self.assertEqual(
                    connection.execute(
                        "SELECT exercise_id FROM workout_exercises WHERE workout_id=1000"
                    ).fetchone()[0],
                    1000,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT exercise_name FROM exercise_logs WHERE workout_log_id=1000"
                    ).fetchone()[0],
                    "Historical move",
                )
                self.assertEqual(
                    connection.execute("SELECT user_id FROM workouts WHERE id=1000").fetchone()[0],
                    1000,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM workouts WHERE name='Bodyweight foundations'"
                    ).fetchone()[0],
                    2,
                )
