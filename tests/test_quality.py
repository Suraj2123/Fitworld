"""Regression cases from the quality review, observed at HTTP and migration seams."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from support import AppCase

from fitworld import create_app
from fitworld.catalog import seed_catalog
from fitworld.db import get_db, migrate


class QualityTest(AppCase):
    def baseline(self, **changes):
        data = {
            "age": 25,
            "weight": 70,
            "unit_system": "metric",
            "experience_level": "beginner",
            "current_workouts_per_week": 0,
        }
        data.update(changes)
        return self.write("onboarding/profile", data, "PUT")

    def test_profile_weight_uses_explicit_local_date(self):
        response = self.baseline(weight=68, measured_on="2025-12-31", record_weight=True)
        self.assertEqual(response.status_code, 200)
        measurements = self.client.get("/api/progress?month=2025-12").json["measurements"]
        self.assertEqual(measurements, [{"measured_on": "2025-12-31", "weight_kg": 68}])

    def test_stale_metadata_edit_preserves_newer_checkin(self):
        today = datetime.now(timezone.utc).date().isoformat()
        self.write(
            "progress/measurements", {"measured_on": today, "weight": 72, "unit_system": "metric"}
        )
        response = self.baseline(age=26, weight=70, record_weight=False, measured_on=today)
        self.assertEqual(response.json["user"]["profile"]["age"], 26)
        self.assertEqual(response.json["user"]["profile"]["weight_kg"], 72)
        measurements = self.client.get(f"/api/progress?month={today[:7]}").json["measurements"]
        self.assertEqual(measurements[-1]["weight_kg"], 72)

    def test_unit_and_habit_changes_do_not_fabricate_measurements(self):
        response = self.baseline(
            unit_system="imperial",
            weight=154.3,
            current_workouts_per_week=2,
            record_weight=False,
            measured_on="2025-12-31",
        )
        self.assertEqual(response.json["user"]["profile"]["weight_kg"], 70)
        self.assertEqual(response.json["user"]["profile"]["unit_system"], "imperial")
        self.assertEqual(self.client.get("/api/progress?month=2025-12").json["measurements"], [])
        self.assertEqual(self.baseline(record_weight="false").status_code, 422)

    def test_all_imported_exercises_are_discoverable_and_names_unique(self):
        guides = self.client.get("/api/exercises").json["exercises"]
        self.assertGreater(len(guides), 40)
        names = [guide["name"].casefold() for guide in guides]
        self.assertEqual(len(names), len(set(names)))
        results = self.client.get("/api/exercises?q=Bench%20Press").json["exercises"]
        self.assertTrue(any(guide["name"] == "Bench Press" for guide in results))
        self.assertTrue(all(guide["description"] for guide in results))
        self.assertEqual(self.app.test_client().get("/api/exercises").status_code, 401)

    def test_bodyweight_equipment_labels_do_not_require_home_equipment(self):
        workouts = self.client.get("/api/workouts").json["workouts"]
        workout = next(row for row in workouts if row["name"] == "Everyday strength")
        self.assertEqual(workout["equipment"], [])

    def test_catalog_edit_does_not_rewrite_historical_muscle_groups(self):
        self.log()
        before = self.day_data()["workouts"][0]["muscle_groups"]
        self.assertTrue(before)
        with self.app.app_context():
            connection = get_db()
            connection.execute(
                "DELETE FROM workout_exercises WHERE workout_id=?", (self.workout["id"],)
            )
            connection.commit()
        after = self.day_data()["workouts"][0]
        self.assertEqual(after["muscle_groups"], before)
        self.assertEqual(after["muscle_groups_source"], "workout_guide")

    def test_legacy_log_without_sets_does_not_invent_historical_groups(self):
        with self.app.app_context():
            connection = get_db()
            connection.execute(
                "INSERT INTO workout_logs (user_id, workout_id, workout_name, performed_on, duration_seconds, status) VALUES (1, ?, 'Old workout', ?, 600, 'completed')",
                (self.workout["id"], self.day),
            )
            connection.commit()
        legacy = self.day_data()["workouts"][0]
        self.assertEqual(legacy["muscle_groups"], [])
        self.assertEqual(legacy["muscle_groups_source"], "not_recorded")

    def test_finished_routine_can_restart_without_losing_old_schedule(self):
        plan = self.client.get("/api/routines").json["routines"][0]
        first = self.write(f"routines/{plan['id']}/select", {"starts_on": "2026-01-05"}).json[
            "current"
        ]
        finished = self.client.get("/api/routines?today=2026-11-04").json["current"]
        self.assertTrue(finished["is_finished"])
        self.assertEqual(finished["ends_on"], "2026-02-01")
        second = self.write(f"routines/{plan['id']}/select", {"starts_on": "2026-11-02"}).json[
            "current"
        ]
        self.assertNotEqual(first["id"], second["id"])
        current = self.client.get("/api/routines?today=2026-11-04").json["current"]
        self.assertFalse(current["is_finished"])
        old_schedule = self.client.get("/api/schedule?from=2026-01-05&to=2026-02-01").json[
            "schedule"
        ]
        self.assertTrue(old_schedule)
        with self.app.app_context():
            self.assertEqual(
                get_db()
                .execute("SELECT status FROM user_routines WHERE id=?", (first["id"],))
                .fetchone()[0],
                "completed",
            )

    def test_identity_upgrade_preserves_references_snapshots_and_guide_notes(self):
        legacy = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE": str(Path(self.directory.name) / "before-identity.sqlite3"),
            }
        )
        with legacy.app_context():
            connection = get_db()
            migrations = Path(__file__).parents[1] / "fitworld/migrations"
            connection.execute(
                "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            for name in (
                "001_initial.sql",
                "002_scheduled_workout_logs.sql",
                "003_add_exercises.sql",
            ):
                connection.executescript((migrations / name).read_text())
                connection.execute("INSERT INTO schema_migrations (version) VALUES (?)", (name,))
                connection.commit()
            connection.execute(
                "INSERT INTO users (id, email, display_name, password_hash) VALUES (1, 'legacy@example.com', 'Legacy', 'existing-hash')"
            )
            connection.execute(
                "INSERT INTO workouts (id, name, intensity, estimated_minutes, category) VALUES (1000, 'Legacy workout', 2, 10, 'strength')"
            )
            connection.execute(
                "INSERT INTO exercises (id, name, muscle_group) VALUES (1000, 'Example movement', 'Original muscle')"
            )
            connection.execute(
                "INSERT INTO exercises (id, name, muscle_group, description) VALUES (1001, 'EXAMPLE MOVEMENT', 'New muscle', 'Contributed guide notes')"
            )
            connection.execute(
                "INSERT INTO workout_exercises (workout_id, exercise_id, position, suggested_reps) VALUES (1000, 1001, 1, 8)"
            )
            connection.execute(
                "INSERT INTO workout_logs (id, user_id, workout_id, workout_name, performed_on, duration_seconds, status) VALUES (1000, 1, 1000, 'Historical name', '2026-01-01', 600, 'completed')"
            )
            connection.execute(
                "INSERT INTO exercise_logs (workout_log_id, exercise_id, exercise_name, muscle_group, set_number, reps) VALUES (1000, 1001, 'Historical movement', 'Historical muscle', 1, 8)"
            )
            connection.commit()
            migrate()
            self.assertEqual(
                connection.execute(
                    "SELECT exercise_id FROM workout_exercises WHERE workout_id=1000"
                ).fetchone()[0],
                1000,
            )
            logged = connection.execute(
                "SELECT * FROM exercise_logs WHERE workout_log_id=1000"
            ).fetchone()
            self.assertEqual(
                (logged["exercise_id"], logged["exercise_name"], logged["muscle_group"]),
                (1000, "Historical movement", "Historical muscle"),
            )
            self.assertEqual(
                connection.execute("SELECT description FROM exercises WHERE id=1000").fetchone()[0],
                "Contributed guide notes",
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO exercises (name, muscle_group) VALUES ('example MOVEMENT', 'Other')"
                )
            connection.rollback()
            seed_catalog(connection)
            seed_catalog(connection)
            self.assertEqual(
                connection.execute(
                    "SELECT lower(name) FROM exercises GROUP BY name COLLATE NOCASE HAVING COUNT(*)>1"
                ).fetchall(),
                [],
            )
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
