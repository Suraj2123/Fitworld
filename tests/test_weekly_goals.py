"""Weekly goals through the authenticated interface shared by Home and Progress."""

from support import AppCase


class WeeklyGoalsTests(AppCase):
    def weekly(self, selected="2026-01-07", today="2026-01-11", client=None, **query):
        return (client or self.client).get(
            "/api/progress/weekly", query_string={"date": selected, "today": today, **query}
        )

    def set_target(self, days):
        return self.write(
            "onboarding/preferences",
            {
                "primary_goal": "build_strength",
                "training_location": "home",
                "target_days_per_week": days,
                "session_minutes": 30,
            },
            "PUT",
        )

    def test_empty_week_uses_saved_target_and_local_monday_to_sunday(self):
        self.set_target(2)
        response = self.weekly()
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["target_days"], 2)
        self.assertEqual(data["target_basis"], "current_preference")
        week = data["week"]
        self.assertEqual((week["starts_on"], week["ends_on"]), ("2026-01-05", "2026-01-11"))
        self.assertEqual(week["completed_days"], 0)
        self.assertEqual(week["remaining_days"], 2)
        self.assertFalse(week["goal_met"])
        self.assertEqual(week["period"], "current")
        self.assertEqual(len(week["days"]), 7)
        self.assertEqual(len(data["history"]), 4)
        self.assertTrue(all(item["completed_days"] == 0 for item in data["history"]))

    def test_completed_days_are_distinct_and_partial_sessions_remain_visible(self):
        self.log()
        self.log()
        self.log(status="partial")
        self.log(performed_on="2026-01-06", status="partial")
        self.log(performed_on="2026-01-07", workout_id=None, workout_name="Walking")
        self.food()
        week = self.weekly().json["week"]
        self.assertEqual(week["completed_days"], 2)
        self.assertEqual(week["remaining_days"], 1)
        self.assertEqual(week["days"][0]["completed_workouts"], 2)
        self.assertEqual(week["days"][0]["partial_workouts"], 1)
        self.assertEqual(week["days"][1]["completed_workouts"], 0)
        self.assertEqual(week["days"][1]["partial_workouts"], 1)
        self.assertFalse(week["goal_met"])

    def test_goal_can_be_met_and_exceeded_without_losing_actual_days(self):
        self.set_target(1)
        self.log()
        self.log(performed_on="2026-01-06")
        week = self.weekly().json["week"]
        self.assertTrue(week["goal_met"])
        self.assertEqual(week["completed_days"], 2)
        self.assertEqual(week["remaining_days"], 0)

    def test_sunday_and_monday_belong_to_different_weeks_across_year_boundary(self):
        self.log(performed_on="2025-12-28")
        self.log(performed_on="2025-12-29")
        self.log(performed_on="2026-01-04")
        self.log(performed_on="2026-01-05")
        data = self.weekly("2026-01-01").json
        self.assertEqual(data["week"]["starts_on"], "2025-12-29")
        self.assertEqual(data["week"]["ends_on"], "2026-01-04")
        self.assertEqual(data["week"]["completed_days"], 2)
        self.assertEqual(data["week"]["period"], "past")
        self.assertEqual(data["history"][0]["completed_days"], 1)
        self.assertEqual(self.weekly().json["week"]["completed_days"], 1)

    def test_week_spanning_leap_day_and_months_counts_all_seven_days(self):
        self.log(performed_on="2024-02-29")
        self.log(performed_on="2024-03-03")
        data = self.weekly("2024-03-01", "2024-03-03").json
        self.assertEqual(data["week"]["starts_on"], "2024-02-26")
        self.assertEqual(data["week"]["ends_on"], "2024-03-03")
        self.assertEqual(data["week"]["completed_days"], 2)

    def test_local_today_excludes_later_logs_and_handles_future_week(self):
        self.log()
        self.log(performed_on="2026-01-06")
        data = self.weekly(today="2026-01-05").json
        self.assertEqual(data["as_of"], "2026-01-05")
        self.assertEqual(data["week"]["completed_days"], 1)
        self.assertFalse(data["week"]["days"][0]["is_future"])
        self.assertTrue(data["week"]["days"][1]["is_future"])
        self.assertEqual(data["week"]["days"][1]["completed_workouts"], 0)
        future = self.weekly("2026-01-12", "2026-01-05").json["week"]
        self.assertEqual(future["period"], "future")
        self.assertEqual(future["completed_days"], 0)
        self.assertFalse(future["goal_met"])

    def test_backdated_logs_and_deletion_recalculate_week_and_history(self):
        first = self.log(performed_on="2025-12-30").json["id"]
        second = self.log(performed_on="2025-12-30").json["id"]
        self.assertEqual(self.weekly().json["history"][0]["completed_days"], 1)
        self.write(f"activity/workouts/{first}", method="DELETE")
        self.assertEqual(self.weekly().json["history"][0]["completed_days"], 1)
        self.write(f"activity/workouts/{second}", method="DELETE")
        self.assertEqual(self.weekly().json["history"][0]["completed_days"], 0)
        self.log()
        self.assertEqual(self.weekly().json["week"]["completed_days"], 1)

    def test_changed_target_recompares_history_without_changing_activity(self):
        self.log(performed_on="2025-12-30")
        self.assertFalse(self.weekly().json["history"][0]["goal_met"])
        self.assertEqual(self.set_target(1).status_code, 200)
        data = self.weekly().json
        self.assertEqual(data["target_basis"], "current_preference")
        self.assertEqual(data["target_days"], 1)
        self.assertTrue(data["history"][0]["goal_met"])
        self.assertEqual(data["history"][0]["completed_days"], 1)

    def test_session_owns_results_and_query_cannot_select_another_account(self):
        self.log()
        other = self.app.test_client()
        self.create_account(other, "other@example.com")
        self.assertEqual(self.weekly(client=other, user_id=1).json["week"]["completed_days"], 0)
        self.assertEqual(self.weekly(user_id=2).json["week"]["completed_days"], 1)

    def test_authentication_and_completed_onboarding_are_required(self):
        other = self.app.test_client()
        self.assertEqual(self.weekly(client=other).status_code, 401)
        self.write(
            "register",
            {"display_name": "New", "email": "new@example.com", "password": "test-password"},
            client=other,
        )
        self.assertEqual(self.weekly(client=other).status_code, 409)

    def test_dates_are_validated_and_supported_range_edges_do_not_break_links(self):
        for value in ("", "2026-02-30", "2026-1-5", "1899-12-31", "2101-01-01"):
            with self.subTest(value=value):
                response = self.weekly(value)
                self.assertEqual(response.status_code, 422)
                self.assertIn("date", response.json["fields"])
        self.assertEqual(self.weekly(today="wrong").status_code, 422)
        early = self.weekly("1900-01-01", "1900-01-01").json
        self.assertEqual(early["history"], [])
        late = self.weekly("2100-12-31", "2100-12-31").json
        self.assertEqual(late["week"]["ends_on"], "2101-01-02")
        self.assertFalse(late["week"]["days"][-1]["is_supported_date"])

    def test_date_defaults_to_explicit_local_today(self):
        response = self.client.get("/api/progress/weekly?today=2026-01-05")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["selected_date"], "2026-01-05")
        self.assertEqual(response.json["week"]["starts_on"], "2026-01-05")
