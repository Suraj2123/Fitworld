"""Read models shared by Home and Progress. Independent aggregates prevent double counting."""

import json

from .activity import NUTRIENTS


def workout_history(connection, user_id, page, per_page):
    """Read one page of the account's logs, newest performed date first."""
    total = connection.execute(
        "SELECT COUNT(*) FROM workout_logs WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    rows = connection.execute(
        """SELECT id, workout_id, workout_name, performed_on, duration_seconds,
                  status, estimated_calories, notes
           FROM workout_logs WHERE user_id=?
           ORDER BY performed_on DESC, started_at DESC, id DESC LIMIT ? OFFSET ?""",
        (user_id, per_page, (page - 1) * per_page),
    ).fetchall()
    return {
        "workouts": [dict(row) for row in rows],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": page * per_page < total,
        },
    }


def daily_activity(connection, user_id, selected_date):
    workouts = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM workout_logs WHERE user_id=? AND performed_on=? ORDER BY started_at DESC, id DESC",
            (user_id, selected_date),
        )
    ]
    muscle_groups = set()
    for workout in workouts:
        workout["exercises"] = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM exercise_logs WHERE workout_log_id=? ORDER BY id", (workout["id"],)
            )
        ]
        snapshot = workout.pop("muscle_groups_snapshot")
        groups = {entry["muscle_group"] for entry in workout["exercises"]}
        source = "recorded_sets" if groups else "not_recorded"
        if snapshot is not None:
            recorded = json.loads(snapshot)
            groups, source = set(recorded["groups"]), recorded["source"]
        workout["muscle_groups_source"] = source
        workout["muscle_groups"] = sorted(groups)
        muscle_groups.update(groups)
    meals = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM nutrition_logs WHERE user_id=? AND consumed_on=? ORDER BY created_at DESC, id DESC",
            (user_id, selected_date),
        )
    ]
    totals = {key: {"known_total": 0.0, "missing_items": 0} for key in NUTRIENTS}
    for meal in meals:
        meal["items"] = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM nutrition_items WHERE nutrition_log_id=? ORDER BY id", (meal["id"],)
            )
        ]
        meal["calories"] = 0
        for item in meal["items"]:
            meal["calories"] += item["servings"] * item["calories_per_serving"]
            for key, column in NUTRIENTS.items():
                if item[column] is None:
                    totals[key]["missing_items"] += 1
                else:
                    totals[key]["known_total"] += item["servings"] * item[column]
    for nutrient in totals.values():
        nutrient["known_total"] = round(nutrient["known_total"], 2)
    return {
        "date": selected_date,
        "workouts": workouts,
        "meals": meals,
        "nutrition": totals,
        "summary": {
            "completed": sum(row["status"] == "completed" for row in workouts),
            "partial": sum(row["status"] == "partial" for row in workouts),
            "duration_minutes": round(sum(row["duration_seconds"] for row in workouts) / 60, 1),
            "estimated_calories_burned": round(
                sum(row["estimated_calories"] or 0 for row in workouts), 1
            ),
            "workouts_missing_calories": sum(row["estimated_calories"] is None for row in workouts),
            "muscle_groups": sorted(muscle_groups),
        },
    }


def recent_activity(connection, user_id):
    return [
        dict(row)
        for row in connection.execute(
            """SELECT id, workout_id, workout_name, performed_on, duration_seconds, status, estimated_calories
           FROM workout_logs WHERE user_id=?
           ORDER BY performed_on DESC, started_at DESC, id DESC LIMIT 8""",
            (user_id,),
        )
    ]


def recent_foods(connection, user_id):
    """Most recently logged nutrition for each food/serving pair, within this account."""
    rows = connection.execute(
        """SELECT * FROM (
            SELECT i.*, ROW_NUMBER() OVER (
                PARTITION BY lower(i.food_name), lower(i.serving_description)
                ORDER BY n.consumed_on DESC, n.id DESC, i.id DESC
            ) AS position
            FROM nutrition_items i JOIN nutrition_logs n ON n.id=i.nutrition_log_id
            WHERE n.user_id=?
        ) WHERE position=1 ORDER BY nutrition_log_id DESC, id DESC LIMIT 20""",
        (user_id,),
    )
    return [dict(row) for row in rows]


def meal_history(connection, user_id, query, start, end, page, category=""):
    """Search meal and food names with bounded, stable pagination."""
    where = """n.user_id=? AND (?='' OR instr(lower(n.meal_name), lower(?))>0 OR EXISTS (
        SELECT 1 FROM nutrition_items i WHERE i.nutrition_log_id=n.id
        AND instr(lower(i.food_name), lower(?))>0))
        AND (?='' OR n.consumed_on>=?) AND (?='' OR n.consumed_on<=?)
        AND (?='' OR n.meal_category=?)"""
    params = (user_id, query, query, query, start, start, end, end, category, category)
    total = connection.execute(
        f"SELECT COUNT(*) FROM nutrition_logs n WHERE {where}", params
    ).fetchone()[0]
    meals = []
    for row in connection.execute(
        f"SELECT n.* FROM nutrition_logs n WHERE {where} ORDER BY n.consumed_on DESC, n.id DESC LIMIT 10 OFFSET ?",
        (*params, (page - 1) * 10),
    ):
        meal = dict(row)
        meal["items"] = [
            dict(item)
            for item in connection.execute(
                "SELECT * FROM nutrition_items WHERE nutrition_log_id=? ORDER BY id", (meal["id"],)
            )
        ]
        meal["calories"] = sum(
            item["servings"] * item["calories_per_serving"] for item in meal["items"]
        )
        meals.append(meal)
    return {
        "meals": meals,
        "pagination": {
            "page": page,
            "total": total,
            "total_pages": (total + 9) // 10,
            "has_next": page * 10 < total,
        },
    }
