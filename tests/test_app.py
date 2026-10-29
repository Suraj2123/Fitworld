"""Exercise the same authenticated JSON interfaces used by all three pages."""

import tempfile
import unittest
from pathlib import Path

from fitworld import create_app
from fitworld.catalog import seed_catalog
from fitworld.db import get_db, migrate


class AppTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only", "DATABASE": str(Path(self.directory.name) / "app.sqlite3")})
        with self.app.app_context():
            migrate()
            seed_catalog(get_db())
        self.client = self.app.test_client()
        self.create_account(self.client, "one@example.com")
        self.workout = next(row for row in self.client.get("/api/workouts").json["workouts"] if row["name"] == "Bodyweight foundations")
        self.day = "2026-01-05"

    def tearDown(self):
        self.directory.cleanup()

    def write(self, path, data=None, method="POST", client=None):
        client = client or self.client
        token = client.get("/api/session").json["csrf_token"]
        return client.open(f"/api/{path}", method=method, json=data if data is not None else {}, headers={"X-CSRF-Token": token})

    def create_account(self, client, email):
        self.write("register", {"display_name": "Test", "email": email, "password": "long-test-password"}, client=client)
        self.write("onboarding/profile", {"age": 25, "weight": 70, "unit_system": "metric", "experience_level": "beginner", "current_workouts_per_week": 0}, "PUT", client)
        self.write("onboarding/preferences", {"primary_goal": "build_strength", "training_location": "home", "target_days_per_week": 3, "session_minutes": 30}, "PUT", client)
        self.write("onboarding/complete", client=client)

    def log(self, **changes):
        data = {"workout_id": self.workout["id"], "performed_on": self.day, "duration_minutes": 20, "status": "completed", "estimated_calories": 100, "notes": "A steady start", "exercises": []}
        data.update(changes)
        return self.write("activity/workouts", data)

    def food(self, **changes):
        item = {"food_name": "Oatmeal", "serving_description": "cup", "servings": 2, "calories_per_serving": 150, "protein_g_per_serving": 5, "carbs_g_per_serving": 27, "fat_g_per_serving": 3, "sodium_mg_per_serving": 0}
        item.update(changes)
        return self.write("activity/meals", {"meal_name": "Breakfast", "consumed_on": self.day, "items": [item]})

    def day_data(self, client=None):
        return (client or self.client).get(f"/api/activity?date={self.day}").json

    def test_pages_and_private_interfaces_require_account_and_completed_setup(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/activity").status_code, 401)
        self.assertEqual(anon.get("/home").status_code, 302)
        self.write("register", {"display_name": "Pending", "email": "pending@example.com", "password": "long-test-password"}, client=anon)
        self.assertEqual(anon.get("/api/workouts").status_code, 409)
        self.assertEqual(anon.get("/workouts").location, "/?setup=1")
        self.assertEqual(self.client.get("/").location, "/home")
        self.assertEqual(self.client.get("/home").status_code, 200)
        self.assertEqual(self.client.get("/workouts").status_code, 200)
        self.assertEqual(self.client.get("/settings").status_code, 200)

    def test_catalog_searches_exercises_and_preserves_seed_edits(self):
        matches = self.client.get("/api/workouts?q=wall%20push").json["workouts"]
        self.assertEqual([row["name"] for row in matches], ["Bodyweight foundations"])
        detail = self.client.get(f'/api/workouts/{self.workout["id"]}').json["workout"]
        self.assertEqual(len(detail["exercises"]), 3)

        with self.app.app_context():
            connection = get_db()
            connection.execute("UPDATE workouts SET description='Team-edited description' WHERE id=?", (self.workout["id"],))
            connection.commit()
            seed_catalog(connection)
        detail = self.client.get(f'/api/workouts/{self.workout["id"]}').json["workout"]
        self.assertEqual(detail["description"], "Team-edited description")
        self.assertEqual(len(detail["exercises"]), 3)

    def test_routine_suggestions_consider_experience_goal_and_weekly_pace(self):
        plans = self.client.get("/api/routines").json["routines"]
        self.assertEqual(plans[0]["name"], "Build your foundation")
        self.write("onboarding/preferences", {"primary_goal": "build_strength", "training_location": "home", "target_days_per_week": 2, "session_minutes": 30}, "PUT")
        self.assertEqual(self.client.get("/api/routines").json["routines"][0]["name"], "A little more movement")

    def test_food_totals_multiply_servings_and_preserve_unknown_nutrients(self):
        self.assertEqual(self.food().status_code, 201)
        self.food(servings=1, protein_g_per_serving=None)
        self.log()
        self.log(status="partial")
        day = self.day_data()
        self.assertEqual(day["nutrition"]["calories"]["known_total"], 450)
        self.assertEqual(day["nutrition"]["protein_g"], {"known_total": 10.0, "missing_items": 1})
        self.assertEqual(day["nutrition"]["sodium_mg"], {"known_total": 0.0, "missing_items": 0})
        self.assertEqual(day["summary"]["estimated_calories_burned"], 200)
        self.assertEqual(day["summary"]["completed"], 1)
        self.assertEqual(day["summary"]["partial"], 1)

    def test_bad_food_input_is_atomic(self):
        for changes in ({"servings": 0}, {"servings": True}, {"calories_per_serving": "NaN"}, {"food_name": " "}, {"protein_g_per_serving": -1}):
            with self.subTest(changes=changes):
                self.assertEqual(self.food(**changes).status_code, 422)
        item = {"food_name": "Rice", "serving_description": "cup", "servings": 1, "calories_per_serving": 200}
        response = self.write("activity/meals", {"meal_name": "Lunch", "consumed_on": self.day, "items": [item, {**item, "servings": -1}]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.day_data()["meals"], [])

    def test_workout_sets_and_partial_status_are_saved(self):
        exercise = self.workout["exercises"][0]
        response = self.log(status="partial", estimated_calories=None, exercises=[{"exercise_id": exercise["exercise_id"], "set_number": 1, "reps": 8, "load_kg": 12.5}])
        self.assertEqual(response.status_code, 201)
        workout = self.day_data()["workouts"][0]
        self.assertEqual(workout["duration_seconds"], 1200)
        self.assertEqual(workout["exercises"][0]["load_kg"], 12.5)
        self.assertEqual(workout["status"], "partial")
        self.assertIsNone(workout["estimated_calories"])
        self.assertEqual(workout["muscle_groups"], ["Legs"])

    def test_latest_home_free_text_workouts_and_removal_keep_totals_separate(self):
        self.food()
        response = self.write("activity/workouts", {"workout_name": "  Walking  ", "performed_on": self.day, "duration_minutes": 30, "status": "completed"})
        self.assertEqual(response.status_code, 201)
        data = self.day_data()
        self.assertEqual(data["workouts"][0]["workout_name"], "Walking")
        self.assertIsNone(data["workouts"][0]["workout_id"])
        self.assertEqual(data["summary"]["duration_minutes"], 30)
        self.assertEqual(data["nutrition"]["calories"]["known_total"], 300)
        self.assertEqual(self.client.get("/api/progress?month=2026-01").json["summary"]["completed_workouts"], 1)
        self.write(f'activity/workouts/{response.json["id"]}', method="DELETE")
        self.assertEqual(self.day_data()["summary"]["duration_minutes"], 0)
        self.assertEqual(self.day_data()["nutrition"]["calories"]["known_total"], 300)

    def test_manual_workout_rejects_blank_names_and_nonpositive_or_fractional_minutes(self):
        data = {"workout_name": "Walk", "performed_on": self.day, "duration_minutes": 20, "status": "completed"}
        for change in ({"workout_name": " "}, {"duration_minutes": 0}, {"duration_minutes": -1}, {"duration_minutes": 1.5}):
            with self.subTest(change=change):
                self.assertEqual(self.write("activity/workouts", {**data, **change}).status_code, 422)
        self.assertEqual(self.day_data()["workouts"], [])

    def test_unknown_exercises_and_invalid_dates_are_rejected(self):
        self.assertEqual(self.log(performed_on="2026-02-30").status_code, 422)
        self.assertEqual(self.log(performed_on="2099-01-01").status_code, 422)
        self.assertEqual(self.log(duration_minutes=-1).status_code, 422)
        self.assertEqual(self.log(exercises=[{"exercise_id": 9999, "set_number": 1, "reps": 8}]).status_code, 422)
        self.assertEqual(self.client.get("/api/activity?date=2026-99-99").status_code, 422)
        self.assertEqual(self.day_data()["workouts"], [])

    def test_routine_selection_is_repeatable_and_replacement_preserves_history(self):
        routines = self.client.get("/api/routines").json["routines"]
        first = next(plan for plan in routines if plan["name"] == "A little more movement")
        second = next(plan for plan in routines if plan["name"] == "Build your foundation")
        path = f'routines/{first["id"]}/select'
        response = self.write(path, {"starts_on": self.day})
        first_enrollment = response.json["current"]["id"]
        self.assertEqual(self.write(path, {"starts_on": self.day}).json["current"]["id"], first_enrollment)
        schedule = self.client.get("/api/schedule?from=2026-01-05&to=2026-02-01").json["schedule"]
        self.assertEqual(len(schedule), 8)
        self.assertTrue(all(row["scheduled_on"] >= self.day for row in schedule))
        self.write(f'routines/{second["id"]}/select', {"starts_on": "2026-01-12"})
        schedule = self.client.get("/api/schedule?from=2026-01-05&to=2026-02-08").json["schedule"]
        old = [row for row in schedule if row["user_routine_id"] == first_enrollment]
        self.assertTrue(all(row["status"] == "skipped" for row in old if row["scheduled_on"] >= "2026-01-12"))
        self.assertTrue(all(row["status"] == "planned" for row in old if row["scheduled_on"] < "2026-01-12"))
        self.assertEqual(self.client.get("/api/routines").json["current"]["routine_id"], second["id"])

    def test_scheduled_completion_can_be_removed_and_relogged(self):
        plan = next(row for row in self.client.get("/api/routines").json["routines"] if row["name"] == "A little more movement")
        self.write(f'routines/{plan["id"]}/select', {"starts_on": self.day})
        scheduled = self.client.get(f"/api/schedule?from={self.day}&to={self.day}").json["schedule"][0]
        response = self.log(scheduled_workout_id=scheduled["id"])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.log(scheduled_workout_id=scheduled["id"]).status_code, 409)
        self.assertEqual(self.client.get(f"/api/schedule?from={self.day}&to={self.day}").json["schedule"][0]["status"], "completed")
        self.assertEqual(self.write(f'activity/workouts/{response.json["id"]}', method="DELETE").status_code, 200)
        self.assertEqual(self.client.get(f"/api/schedule?from={self.day}&to={self.day}").json["schedule"][0]["status"], "planned")
        self.assertEqual(self.log(scheduled_workout_id=scheduled["id"]).status_code, 201)

    def test_other_accounts_cannot_read_delete_or_link_private_entries(self):
        workout_id = self.log().json["id"]
        meal_id = self.food().json["id"]
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        self.assertEqual(self.day_data(other)["workouts"], [])
        self.assertEqual(self.day_data(other)["meals"], [])
        self.assertEqual(self.write(f"activity/workouts/{workout_id}", method="DELETE", client=other).status_code, 404)
        self.assertEqual(self.write(f"activity/meals/{meal_id}", method="DELETE", client=other).status_code, 404)
        self.assertEqual(len(self.day_data()["workouts"]), 1)

    def test_upgrade_preserves_existing_user_and_workout_history(self):
        legacy = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(Path(self.directory.name) / "legacy.sqlite3")})
        with legacy.app_context():
            connection = get_db()
            connection.executescript((Path(__file__).parents[1] / "fitworld/migrations/001_initial.sql").read_text())
            connection.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("INSERT INTO schema_migrations (version) VALUES ('001_initial.sql')")
            connection.execute("INSERT INTO users (id, email, display_name, password_hash) VALUES (1, 'legacy@example.com', 'Legacy', 'existing-hash')")
            connection.execute("INSERT INTO workout_logs (id, user_id, workout_name, performed_on, duration_seconds, status) VALUES (12, 1, 'Original workout', '2026-01-01', 300, 'partial')")
            connection.commit()
            migrate()
            row = connection.execute("SELECT * FROM workout_logs WHERE id=12").fetchone()
            self.assertEqual(row["workout_name"], "Original workout")
            self.assertIsNone(row["scheduled_workout_id"])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_progress_counts_complete_and_partial_days_without_nutrition_multiplication(self):
        self.log()
        self.log(status="partial", performed_on="2026-01-06", duration_minutes=10)
        self.food()
        self.food(servings=1)
        response = self.client.get("/api/progress?month=2026-01&today=2026-02-01")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["summary"]["completed_workouts"], 1)
        self.assertEqual(data["summary"]["partial_workouts"], 1)
        self.assertEqual(data["summary"]["duration_minutes"], 30)
        self.assertEqual(data["summary"]["active_days"], 2)
        self.assertEqual(data["summary"]["average_per_week"], 0.2)
        day = next(row for row in data["days"] if row["date"] == self.day)
        self.assertEqual(day["completed"], 1)
        self.assertEqual(day["meals"], 2)
        self.assertEqual(next(row for row in data["days"] if row["date"] == "2026-01-06")["partial"], 1)
        self.assertEqual(self.client.get("/progress").status_code, 200)

    def test_month_to_date_average_uses_elapsed_calendar_days(self):
        for _ in range(3):
            self.log()
        summary = self.client.get("/api/progress?month=2026-01&today=2026-01-10").json["summary"]
        self.assertEqual(summary["average_per_week"], 2.1)
        self.assertEqual(summary["average_window_days"], 10)
        self.assertEqual(summary["average_window"], "month_to_date")

    def test_calendar_handles_leap_year_and_year_boundary_and_empty_months(self):
        february = self.client.get("/api/progress?month=2024-02").json
        self.assertEqual(len(february["days"]), 29)
        self.assertEqual(february["ends_on"], "2024-02-29")
        self.assertEqual(february["summary"]["completed_workouts"], 0)
        december = self.client.get("/api/progress?month=2026-12").json
        self.assertEqual(december["ends_on"], "2026-12-31")
        for invalid in ("2026-13", "2026-1", "bad", "1899-12"):
            self.assertEqual(self.client.get(f"/api/progress?month={invalid}").status_code, 422)

    def test_exercise_records_compare_prior_best_and_exclude_partial_and_later_months(self):
        exercise = self.workout["exercises"][0]["exercise_id"]
        def sets(load, seconds):
            return [{"exercise_id": exercise, "set_number": 1, "reps": 8, "load_kg": load, "duration_seconds": seconds}]
        self.log(performed_on="2025-12-30", exercises=sets(10, 30))
        self.log(exercises=sets(15, 45))
        self.log(status="partial", exercises=sets(100, 600))
        self.log(performed_on="2026-02-01", exercises=sets(30, 90))
        records = self.client.get("/api/progress?month=2026-01").json["records"]
        load = next(row for row in records if row["metric"] == "load_kg")
        seconds = next(row for row in records if row["metric"] == "duration_seconds")
        self.assertEqual((load["value"], load["previous_best"], load["improvement"]), (15, 10, 5))
        self.assertEqual((seconds["value"], seconds["previous_best"], seconds["improvement"]), (45, 30, 15))

    def test_first_benchmark_does_not_invent_an_improvement(self):
        exercise = self.workout["exercises"][0]["exercise_id"]
        self.log(exercises=[{"exercise_id": exercise, "set_number": 1, "reps": 8, "load_kg": 15}])
        record = self.client.get("/api/progress?month=2026-01").json["records"][0]
        self.assertIsNone(record["previous_best"])
        self.assertIsNone(record["improvement"])

    def test_progress_and_measurements_are_private_and_backdating_keeps_current_profile(self):
        self.log()
        self.assertEqual(self.write("progress/measurements", {"measured_on": "2026-01-01", "weight": 154.3, "unit_system": "imperial"}).status_code, 201)
        self.write("progress/measurements", {"measured_on": "2026-01-02", "weight": 69, "unit_system": "metric"})
        self.write("progress/measurements", {"measured_on": "2026-01-02", "weight": 68, "unit_system": "metric"})
        progress = self.client.get("/api/progress?month=2026-01").json
        self.assertEqual(len(progress["measurements"]), 2)
        self.assertAlmostEqual(progress["measurements"][0]["weight_kg"], 69.989, places=3)
        self.assertEqual(progress["measurements"][1]["weight_kg"], 68)
        self.assertEqual(self.client.get("/api/session").json["user"]["profile"]["weight_kg"], 70)
        other = self.app.test_client()
        self.create_account(other, "two@example.com")
        other_progress = other.get("/api/progress?month=2026-01").json
        self.assertEqual(other_progress["summary"]["completed_workouts"], 0)
        self.assertEqual(other_progress["measurements"], [])
        self.assertEqual(other_progress["records"], [])

    def test_deleting_activity_updates_calendar_and_nutrition(self):
        workout = self.log().json["id"]
        meal = self.food().json["id"]
        self.write(f"activity/workouts/{workout}", method="DELETE")
        self.write(f"activity/meals/{meal}", method="DELETE")
        data = self.client.get("/api/progress?month=2026-01").json
        self.assertEqual(data["summary"]["completed_workouts"], 0)
        day = next(row for row in data["days"] if row["date"] == self.day)
        self.assertEqual(day["meals"], 0)
        self.assertEqual(self.day_data()["nutrition"]["calories"]["known_total"], 0)


if __name__ == "__main__":
    unittest.main()
