"""Weekly workout-day goals, shared by Home and Progress without storing derived counts."""

from datetime import date, timedelta

HISTORY_WEEKS = 4


def weekly_progress(connection, user_id, selected_date, today):
    """Read a selected week and four preceding weeks against the current saved target.

    Dates are validated local YYYY-MM-DD values supplied by the HTTP adapter. A day
    counts once if it has any completed workout. Partial sessions remain visible,
    and activity after the caller's local today is excluded. This function only
    reads; late entries and deletions are reflected without synchronizing counters.
    """
    selected = date.fromisoformat(selected_date)
    as_of = date.fromisoformat(today)
    monday = selected - timedelta(days=selected.weekday())
    starts = [monday - timedelta(weeks=offset) for offset in range(HISTORY_WEEKS + 1)]
    starts = [start for start in starts if start.year >= 1900]
    preference = connection.execute(
        "SELECT target_days_per_week FROM workout_preferences WHERE user_id=?", (user_id,)
    ).fetchone()
    target = preference["target_days_per_week"]
    activity = {
        row["performed_on"]: row
        for row in connection.execute(
            """
            SELECT performed_on,
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status='partial' THEN 1 ELSE 0 END) AS partial
            FROM workout_logs
            WHERE user_id=? AND performed_on>=? AND performed_on<? AND performed_on<=?
            GROUP BY performed_on
            """,
            (user_id, starts[-1].isoformat(), (monday + timedelta(days=7)).isoformat(), today),
        )
    }

    def week(start):
        end = start + timedelta(days=6)
        days = []
        for offset in range(7):
            current = start + timedelta(days=offset)
            row = activity.get(current.isoformat())
            days.append(
                {
                    "date": current.isoformat(),
                    "completed_workouts": row["completed"] if row else 0,
                    "partial_workouts": row["partial"] if row else 0,
                    "is_future": current > as_of,
                    "is_supported_date": 1900 <= current.year <= 2100,
                }
            )
        completed = sum(day["completed_workouts"] > 0 for day in days)
        return {
            "starts_on": start.isoformat(),
            "ends_on": end.isoformat(),
            "period": "future" if start > as_of else "past" if end < as_of else "current",
            "completed_days": completed,
            "remaining_days": max(0, target - completed),
            "goal_met": completed >= target,
            "days": days,
        }

    weeks = [week(start) for start in starts]
    return {
        "selected_date": selected_date,
        "as_of": today,
        "target_days": target,
        "target_basis": "current_preference",
        "week": weeks[0],
        "history": weeks[1:],
    }
