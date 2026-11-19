import tempfile
from pathlib import Path

from support import AppCase

from fitworld import create_app
from fitworld.db import get_db, migrate


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

    def test_favorite_is_private_snapshot_not_a_second_log(self):
        meal_id = self.food().json["id"]
        favorite = self.write("meals/favorites", {"meal_id": meal_id})
        self.assertEqual(favorite.status_code, 201)
        favorite_id = favorite.json["id"]
        self.assertEqual(self.write("meals/favorites", {"meal_id": meal_id}).status_code, 409)
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        self.assertEqual(other.get("/api/meals/favorites").json["meals"], [])
        self.assertEqual(
            self.write("meals/favorites", {"meal_id": meal_id}, client=other).status_code, 404
        )
        self.assertEqual(
            self.write(f"meals/favorites/{favorite_id}", method="DELETE", client=other).status_code,
            404,
        )
        self.write(f"activity/meals/{meal_id}", self.meal_payload(), "PUT")
        self.write(f"activity/meals/{meal_id}", method="DELETE")
        saved = self.client.get("/api/meals/favorites").json["meals"]
        self.assertEqual(saved[0]["items"][0]["servings"], 2)
        self.assertEqual(self.day_data()["meals"], [])
        self.assertEqual(
            self.write(f"meals/favorites/{favorite_id}", method="DELETE").status_code, 200
        )

    def test_meal_search_matches_food_and_dates_with_stable_pagination(self):
        for _ in range(12):
            self.food()
        page = self.client.get("/api/activity/meals?q=oat&from=2026-01-05&to=2026-01-05").json
        self.assertEqual(len(page["meals"]), 10)
        self.assertTrue(page["pagination"]["has_next"])
        second = self.client.get("/api/activity/meals?q=oat&page=2").json
        self.assertEqual(len(second["meals"]), 2)
        self.assertFalse(
            set(row["id"] for row in page["meals"]) & set(row["id"] for row in second["meals"])
        )
        self.assertEqual(self.client.get("/api/activity/meals?q=%25").json["meals"], [])
        self.assertEqual(self.client.get("/api/activity/meals?from=2026-01-06").json["meals"], [])
        self.assertEqual(self.client.get("/api/activity/meals?page=0").status_code, 422)
        self.assertEqual(
            self.client.get("/api/activity/meals?from=2026-02-01&to=2026-01-01").status_code, 422
        )
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        self.assertEqual(other.get("/api/activity/meals?q=oat").json["meals"], [])

    def test_meal_categories_preserve_defaults_and_follow_edits_and_favorites(self):
        old_id = self.food().json["id"]
        self.assertEqual(self.day_data()["meals"][0]["meal_category"], "uncategorized")
        data = self.meal_payload(meal_category="lunch")
        self.assertEqual(self.write(f"activity/meals/{old_id}", data, "PUT").status_code, 200)
        self.write("meals/favorites", {"meal_id": old_id})
        self.assertEqual(
            self.client.get("/api/meals/favorites").json["meals"][0]["meal_category"], "lunch"
        )
        self.assertEqual(
            len(self.client.get("/api/activity/meals?meal_category=lunch").json["meals"]), 1
        )
        self.assertEqual(
            self.client.get("/api/activity/meals?meal_category=dinner").json["meals"], []
        )
        self.assertEqual(
            self.write("activity/meals", self.meal_payload(meal_category="invalid")).status_code,
            422,
        )
        self.assertEqual(
            self.client.get("/api/activity/meals?meal_category=invalid").status_code, 422
        )

    def test_populated_upgrade_preserves_meals_items_and_favorite_snapshots(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app(
                {
                    "TESTING": True,
                    "SECRET_KEY": "test-only",
                    "DATABASE": str(Path(folder) / "old.sqlite3"),
                }
            )
            with app.app_context():
                db = get_db()
                db.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)")
                migrations = Path(__file__).parents[1] / "fitworld/migrations"
                for path in sorted(migrations.glob("*.sql")):
                    if path.name.startswith("009_"):
                        break
                    db.executescript(path.read_text())
                    db.execute("INSERT INTO schema_migrations VALUES (?)", (path.name,))
                    db.commit()
                db.execute(
                    "INSERT INTO users (id,email,display_name,password_hash) VALUES (1000,'old@example.com','Old','hash')"
                )
                db.execute(
                    "INSERT INTO nutrition_logs (id,user_id,consumed_on,meal_name,source) VALUES (1000,1000,'2026-01-05','Lunch','manual')"
                )
                db.execute(
                    "INSERT INTO nutrition_items (id,nutrition_log_id,food_name,serving_description,servings,calories_per_serving) VALUES (1000,1000,'Oats','cup',2,150)"
                )
                db.execute(
                    "INSERT INTO favorite_meals (id,user_id,name,items_json) VALUES (1000,1000,'Old favorite','[]')"
                )
                db.commit()
                migrate()
                migrate()
                meal = db.execute("SELECT * FROM nutrition_logs WHERE id=1000").fetchone()
                self.assertEqual(
                    (meal["meal_name"], meal["meal_category"]), ("Lunch", "uncategorized")
                )
                item = db.execute("SELECT * FROM nutrition_items WHERE id=1000").fetchone()
                self.assertEqual(
                    (item["nutrition_log_id"], item["servings"], item["calories_per_serving"]),
                    (1000, 2, 150),
                )
                favorite = db.execute("SELECT * FROM favorite_meals WHERE id=1000").fetchone()
                self.assertEqual(
                    (favorite["name"], favorite["items_json"], favorite["meal_category"]),
                    ("Old favorite", "[]", "uncategorized"),
                )
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
