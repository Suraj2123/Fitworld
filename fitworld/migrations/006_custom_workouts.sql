-- Alter table to allow for custom workouts/execises specific to the user
ALTER TABLE workouts ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE exercises ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

-- Index on exercises to see if exercises is a part of catalog, or created by user
-- Exercises created by users must be unique
CREATE UNIQUE INDEX exercises_name_per_user
ON exercises(name COLLATE NOCASE, COALESCE(user_id, 0));