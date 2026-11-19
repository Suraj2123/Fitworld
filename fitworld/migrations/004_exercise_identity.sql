-- Preserve the oldest identity and all logged name/muscle snapshots.
-- Migration 003 remains unchanged for databases that have already applied it.
UPDATE exercises
SET description = COALESCE(NULLIF(description, ''), (
    SELECT other.description FROM exercises other
    WHERE other.name = exercises.name COLLATE NOCASE AND other.description != ''
    ORDER BY other.id LIMIT 1
), '');

UPDATE workout_exercises
SET exercise_id = (
    SELECT MIN(canonical.id) FROM exercises canonical
    WHERE canonical.name = (SELECT name FROM exercises WHERE id = exercise_id) COLLATE NOCASE
);

UPDATE exercise_logs
SET exercise_id = (
    SELECT MIN(canonical.id) FROM exercises canonical
    WHERE canonical.name = (SELECT name FROM exercises WHERE id = exercise_id) COLLATE NOCASE
)
WHERE exercise_id IS NOT NULL;

DELETE FROM exercises
WHERE id NOT IN (SELECT MIN(id) FROM exercises GROUP BY name COLLATE NOCASE);

CREATE UNIQUE INDEX exercises_name_case_insensitive ON exercises(name COLLATE NOCASE);
