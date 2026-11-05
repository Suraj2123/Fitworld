"""Exercise the same authenticated JSON interfaces used by all three pages."""

import tempfile
import unittest
from pathlib import Path

from fitworld import create_app
from fitworld.catalog import seed_catalog
from fitworld.db import get_db, migrate


class AppCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-only",
                "DATABASE": str(Path(self.directory.name) / "app.sqlite3"),
            }
        )
        with self.app.app_context():
            migrate()
            seed_catalog(get_db())
        self.client = self.app.test_client()
        self.create_account(self.client, "one@example.com")
        self.workout = next(
            row
            for row in self.client.get("/api/workouts").json["workouts"]
            if row["name"] == "Bodyweight foundations"
        )
        self.day = "2026-01-05"

    def tearDown(self):
        self.directory.cleanup()

    def write(self, path, data=None, method="POST", client=None):
        client = client or self.client
        token = client.get("/api/session").json["csrf_token"]
        return client.open(
            f"/api/{path}",
            method=method,
            json=data if data is not None else {},
            headers={"X-CSRF-Token": token},
        )

    def create_account(self, client, email):
        self.write(
            "register",
            {"display_name": "Test", "email": email, "password": "long-test-password"},
            client=client,
        )
        self.write(
            "onboarding/profile",
            {
                "age": 25,
                "weight": 70,
                "unit_system": "metric",
                "experience_level": "beginner",
                "current_workouts_per_week": 0,
            },
            "PUT",
            client,
        )
        self.write(
            "onboarding/preferences",
            {
                "primary_goal": "build_strength",
                "training_location": "home",
                "target_days_per_week": 3,
                "session_minutes": 30,
            },
            "PUT",
            client,
        )
        self.write("onboarding/complete", client=client)

    def log(self, **changes):
        data = {
            "workout_id": self.workout["id"],
            "performed_on": self.day,
            "duration_minutes": 20,
            "status": "completed",
            "estimated_calories": 100,
            "notes": "A steady start",
            "exercises": [],
        }
        data.update(changes)
        return self.write("activity/workouts", data)

    def food(self, **changes):
        item = {
            "food_name": "Oatmeal",
            "serving_description": "cup",
            "servings": 2,
            "calories_per_serving": 150,
            "protein_g_per_serving": 5,
            "carbs_g_per_serving": 27,
            "fat_g_per_serving": 3,
            "sodium_mg_per_serving": 0,
        }
        item.update(changes)
        return self.write(
            "activity/meals", {"meal_name": "Breakfast", "consumed_on": self.day, "items": [item]}
        )

    def day_data(self, client=None):
        return (client or self.client).get(f"/api/activity?date={self.day}").json
