"""Private meal templates copied from saved meals, independent of daily activity."""

import json

from werkzeug.exceptions import Conflict, NotFound

from .activity import NUTRIENTS
from .validation import Form


def favorites(connection, user_id):
    return [
        {"id": row["id"], "meal_name": row["name"], "items": json.loads(row["items_json"])}
        for row in connection.execute(
            "SELECT * FROM favorite_meals WHERE user_id=? ORDER BY name, id", (user_id,)
        )
    ]


def save_favorite(connection, user_id, data):
    form = Form(data)
    meal_id = form.number("meal_id", "saved meal", 1, 2**53, integer=True)
    form.finish()
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        meal = connection.execute(
            "SELECT * FROM nutrition_logs WHERE id=? AND user_id=?", (meal_id, user_id)
        ).fetchone()
        if meal is None:
            raise NotFound("This meal was not found in your account.")
        name = meal["meal_name"]
        if connection.execute(
            "SELECT 1 FROM favorite_meals WHERE user_id=? AND name=?", (user_id, name)
        ).fetchone():
            raise Conflict(
                "A favorite with this name already exists. Remove it to save a new version."
            )
        if (
            connection.execute(
                "SELECT COUNT(*) FROM favorite_meals WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            >= 100
        ):
            raise Conflict("You can save up to 100 favorites. Remove one before adding another.")
        fields = ["food_name", "serving_description", "servings", *NUTRIENTS.values()]
        items = [
            {key: row[key] for key in fields}
            for row in connection.execute(
                "SELECT * FROM nutrition_items WHERE nutrition_log_id=? ORDER BY id", (meal_id,)
            )
        ]
        return connection.execute(
            "INSERT INTO favorite_meals (user_id, name, items_json) VALUES (?, ?, ?)",
            (user_id, name, json.dumps(items)),
        ).lastrowid


def delete_favorite(connection, user_id, favorite_id):
    with connection:
        cursor = connection.execute(
            "DELETE FROM favorite_meals WHERE id=? AND user_id=?", (favorite_id, user_id)
        )
        if not cursor.rowcount:
            raise NotFound("This favorite was not found in your account.")
