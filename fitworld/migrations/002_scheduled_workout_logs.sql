-- Additive: old logs remain valid and retain their existing IDs and snapshots.
ALTER TABLE workout_logs ADD COLUMN scheduled_workout_id INTEGER
    REFERENCES scheduled_workouts(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX one_completed_log_per_schedule
    ON workout_logs(scheduled_workout_id)
    WHERE scheduled_workout_id IS NOT NULL AND status = 'completed';

CREATE TRIGGER scheduled_log_owner_insert
BEFORE INSERT ON workout_logs WHEN NEW.scheduled_workout_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Scheduled workout must belong to this user and workout')
    WHERE NOT EXISTS (
        SELECT 1 FROM scheduled_workouts s WHERE s.id = NEW.scheduled_workout_id
        AND s.user_id = NEW.user_id AND s.workout_id = NEW.workout_id
        AND s.scheduled_on = NEW.performed_on
    );
END;

CREATE TRIGGER scheduled_log_owner_update
BEFORE UPDATE OF scheduled_workout_id, user_id, workout_id, performed_on ON workout_logs
WHEN NEW.scheduled_workout_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Scheduled workout must belong to this user and workout')
    WHERE NOT EXISTS (
        SELECT 1 FROM scheduled_workouts s WHERE s.id = NEW.scheduled_workout_id
        AND s.user_id = NEW.user_id AND s.workout_id = NEW.workout_id
        AND s.scheduled_on = NEW.performed_on
    );
END;
