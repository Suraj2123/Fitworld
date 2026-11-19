-- fitworld: rebuild-parent-tables
-- Migration 006 is already shared. Replace its inherited global name constraints
-- with owner-scoped identities while preserving every ID, prescription and log.
-- The runner checks foreign keys before committing and restores enforcement.

CREATE TABLE exercises_rebuilt (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    muscle_group TEXT NOT NULL,
    equipment TEXT NOT NULL DEFAULT 'none',
    image_path TEXT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
);
INSERT INTO exercises_rebuilt
SELECT id, name, description, muscle_group, equipment, image_path, user_id FROM exercises;
DROP TABLE exercises;
ALTER TABLE exercises_rebuilt RENAME TO exercises;
CREATE UNIQUE INDEX exercises_name_per_user
ON exercises(name COLLATE NOCASE, COALESCE(user_id, 0));
CREATE INDEX exercises_owner ON exercises(user_id);

CREATE TABLE workouts_rebuilt (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    intensity INTEGER NOT NULL CHECK (typeof(intensity) = 'integer' AND intensity BETWEEN 1 AND 10),
    estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes > 0),
    category TEXT NOT NULL CHECK (category IN ('strength', 'cardio', 'mobility', 'recovery', 'mixed')),
    image_path TEXT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
);
INSERT INTO workouts_rebuilt
SELECT id, name, description, intensity, estimated_minutes, category, image_path, user_id FROM workouts;
DROP TABLE workouts;
ALTER TABLE workouts_rebuilt RENAME TO workouts;
-- Preserve the existing exact-name workout identity, now scoped to its owner.
CREATE UNIQUE INDEX workouts_name_per_user ON workouts(name, COALESCE(user_id, 0));
CREATE INDEX workouts_owner ON workouts(user_id);
