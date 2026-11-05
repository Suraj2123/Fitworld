"""Weight writes shared by onboarding and later check-ins."""

from .validation import Form, body_weight, iso_date


def upsert_measurement(connection, user_id, kilograms, measured_on):
    """Caller owns the transaction; update a day and synchronize the latest weight."""
    connection.execute(
        """INSERT INTO body_measurements (user_id, measured_on, weight_kg)
           VALUES (?, ?, ?) ON CONFLICT(user_id, measured_on)
           DO UPDATE SET weight_kg=excluded.weight_kg""",
        (user_id, measured_on, kilograms),
    )
    latest = connection.execute(
        "SELECT weight_kg FROM body_measurements WHERE user_id=? ORDER BY measured_on DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    connection.execute(
        "UPDATE user_profiles SET weight_kg=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
        (latest["weight_kg"], user_id),
    )


def record_weight(connection, user_id, data):
    form = Form(data)
    kilograms, _units = body_weight(form)
    form.finish()
    measured_on = iso_date(data.get("measured_on"), "measured_on", historical=True)
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        upsert_measurement(connection, user_id, kilograms, measured_on)
    return {"measured_on": measured_on, "weight_kg": kilograms}
