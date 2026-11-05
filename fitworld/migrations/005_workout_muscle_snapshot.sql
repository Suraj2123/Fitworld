-- NULL means a legacy log did not capture this information; do not invent history.
ALTER TABLE workout_logs ADD COLUMN muscle_groups_snapshot TEXT;
