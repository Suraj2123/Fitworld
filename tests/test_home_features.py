from support import AppCase


class HomeFeatureTests(AppCase):
    def meal_payload(self, **changes):
        data = {
            "meal_name": "Breakfast",
            "consumed_on": self.day,
            "items": [
                {
                    "food_name": "Oats",
                    "serving_description": "cup",
                    "servings": 1,
                    "calories_per_serving": 150,
                }
            ],
        }
        data.update(changes)
        return data

    def test_edit_meal_preserves_id_and_recalculates_totals(self):
        log_id = self.food().json["id"]
        response = self.write(f"activity/meals/{log_id}", self.meal_payload(), "PUT")
        self.assertEqual(response.status_code, 200)
        day = self.day_data()
        self.assertEqual(day["meals"][0]["id"], log_id)
        self.assertEqual(len(day["meals"]), 1)
        self.assertEqual(day["nutrition"]["calories"]["known_total"], 150)
        self.assertEqual(day["nutrition"]["protein_g"]["missing_items"], 1)

    def test_invalid_or_foreign_meal_edit_leaves_original_intact(self):
        log_id = self.food().json["id"]
        response = self.write(f"activity/meals/{log_id}", self.meal_payload(items=[]), "PUT")
        self.assertEqual(response.status_code, 422)
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        response = self.write(f"activity/meals/{log_id}", self.meal_payload(), "PUT", other)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.day_data()["nutrition"]["calories"]["known_total"], 300)

    def test_recent_foods_use_latest_values_and_keep_accounts_separate(self):
        self.food(calories_per_serving=150)
        self.food(calories_per_serving=200)
        foods = self.client.get("/api/foods/recent").json["foods"]
        self.assertEqual(len(foods), 1)
        self.assertEqual(foods[0]["calories_per_serving"], 200)
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        self.assertEqual(other.get("/api/foods/recent").json["foods"], [])

    def test_manual_workout_edit_preserves_date_and_updates_weekly_goal(self):
        log_id = self.log(workout_id=None, workout_name="Walk").json["id"]
        payload = {
            "workout_name": "Walk corrected",
            "duration_minutes": 15,
            "status": "partial",
            "notes": "Rain",
            "estimated_calories": "",
        }
        self.assertEqual(self.write(f"activity/workouts/{log_id}", payload, "PUT").status_code, 200)
        day = self.day_data()
        self.assertEqual(day["workouts"][0]["id"], log_id)
        self.assertEqual(day["workouts"][0]["performed_on"], self.day)
        self.assertEqual(day["summary"]["completed"], 0)
        self.assertEqual(day["summary"]["duration_minutes"], 15)
        self.assertIsNone(day["workouts"][0]["estimated_calories"])
        goal = self.client.get(f"/api/progress/weekly?date={self.day}&today={self.day}").json
        self.assertEqual(goal["week"]["completed_days"], 0)
        catalog_id = self.log().json["id"]
        self.assertEqual(
            self.write(f"activity/workouts/{catalog_id}", payload, "PUT").status_code, 409
        )
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        self.assertEqual(
            self.write(f"activity/workouts/{log_id}", payload, "PUT", other).status_code, 404
        )
        payload["duration_minutes"] = -1
        self.assertEqual(self.write(f"activity/workouts/{log_id}", payload, "PUT").status_code, 422)
        self.assertEqual(self.day_data()["summary"]["duration_minutes"], 35)
