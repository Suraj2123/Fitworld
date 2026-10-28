-- SQLite 3.24+. All timestamps are UTC; calendar dates are YYYY-MM-DD.
-- Enable PRAGMA foreign_keys = ON on EVERY connection (including C++ clients).

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(email) BETWEEN 3 AND 254),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) BETWEEN 1 AND 80),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    onboarding_completed_at TEXT
);

CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    age INTEGER NOT NULL CHECK (typeof(age) = 'integer' AND age BETWEEN 13 AND 120),
    weight_kg REAL NOT NULL CHECK (weight_kg BETWEEN 20 AND 400),
    unit_system TEXT NOT NULL CHECK (unit_system IN ('metric', 'imperial')),
    experience_level TEXT NOT NULL CHECK (experience_level IN ('beginner', 'intermediate', 'advanced')),
    current_workouts_per_week INTEGER NOT NULL CHECK (
        typeof(current_workouts_per_week) = 'integer' AND current_workouts_per_week BETWEEN 0 AND 7
    ),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workout_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    primary_goal TEXT NOT NULL CHECK (primary_goal IN ('get_active', 'build_strength', 'improve_endurance', 'improve_mobility')),
    training_location TEXT NOT NULL CHECK (training_location IN ('home', 'gym', 'outdoors')),
    target_days_per_week INTEGER NOT NULL CHECK (
        typeof(target_days_per_week) = 'integer' AND target_days_per_week BETWEEN 1 AND 7
    ),
    session_minutes INTEGER NOT NULL CHECK (session_minutes IN (15, 30, 45, 60, 90)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE body_measurements (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    measured_on TEXT NOT NULL,
    weight_kg REAL NOT NULL CHECK (weight_kg BETWEEN 20 AND 400),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, measured_on)
);

-- Shared exercise/workout/routine catalog. Private records always carry user_id.
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    muscle_group TEXT NOT NULL,
    equipment TEXT NOT NULL DEFAULT 'none',
    image_path TEXT
);

CREATE TABLE workouts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    intensity INTEGER NOT NULL CHECK (typeof(intensity) = 'integer' AND intensity BETWEEN 1 AND 10),
    estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes > 0),
    category TEXT NOT NULL CHECK (category IN ('strength', 'cardio', 'mobility', 'recovery', 'mixed')),
    image_path TEXT
);

CREATE TABLE workout_exercises (
    id INTEGER PRIMARY KEY,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
    position INTEGER NOT NULL CHECK (position >= 1),
    suggested_sets INTEGER NOT NULL DEFAULT 1 CHECK (suggested_sets > 0),
    suggested_reps INTEGER CHECK (suggested_reps > 0),
    suggested_seconds INTEGER CHECK (suggested_seconds > 0),
    CHECK (suggested_reps IS NOT NULL OR suggested_seconds IS NOT NULL),
    UNIQUE (workout_id, position)
);
CREATE INDEX workout_exercises_exercise ON workout_exercises(exercise_id);

CREATE TABLE routines (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    experience_level TEXT NOT NULL CHECK (experience_level IN ('beginner', 'intermediate', 'advanced')),
    duration_weeks INTEGER NOT NULL CHECK (duration_weeks > 0)
);

CREATE TABLE routine_workouts (
    id INTEGER PRIMARY KEY,
    routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE RESTRICT,
    week_number INTEGER NOT NULL CHECK (week_number >= 1),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7), -- Monday = 1
    position INTEGER NOT NULL DEFAULT 1 CHECK (position >= 1),
    UNIQUE (routine_id, week_number, day_of_week, position)
);
CREATE INDEX routine_workouts_workout ON routine_workouts(workout_id);

CREATE TABLE user_routines (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE RESTRICT,
    starts_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'replaced')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, user_id)
);
CREATE UNIQUE INDEX one_active_routine_per_user ON user_routines(user_id) WHERE status = 'active';
CREATE INDEX user_routines_routine ON user_routines(routine_id);

CREATE TABLE scheduled_workouts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_routine_id INTEGER,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE RESTRICT,
    scheduled_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'skipped')),
    FOREIGN KEY (user_routine_id, user_id) REFERENCES user_routines(id, user_id) ON DELETE CASCADE,
    UNIQUE (id, user_id)
);
CREATE INDEX scheduled_workouts_calendar ON scheduled_workouts(user_id, scheduled_on);
CREATE INDEX scheduled_workouts_routine ON scheduled_workouts(user_routine_id, user_id);
CREATE INDEX scheduled_workouts_workout ON scheduled_workouts(workout_id);

CREATE TABLE workout_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workout_id INTEGER REFERENCES workouts(id) ON DELETE SET NULL,
    workout_name TEXT NOT NULL, -- Snapshot survives changes to the catalog.
    performed_on TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds >= 0),
    status TEXT NOT NULL CHECK (status IN ('completed', 'partial')),
    estimated_calories REAL CHECK (estimated_calories >= 0),
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX workout_logs_calendar ON workout_logs(user_id, performed_on);
CREATE INDEX workout_logs_workout ON workout_logs(workout_id);

CREATE TABLE exercise_logs (
    id INTEGER PRIMARY KEY,
    workout_log_id INTEGER NOT NULL REFERENCES workout_logs(id) ON DELETE CASCADE,
    exercise_id INTEGER REFERENCES exercises(id) ON DELETE SET NULL,
    exercise_name TEXT NOT NULL,
    muscle_group TEXT NOT NULL,
    set_number INTEGER NOT NULL CHECK (set_number >= 1),
    reps INTEGER CHECK (reps >= 0),
    duration_seconds INTEGER CHECK (duration_seconds >= 0),
    load_kg REAL CHECK (load_kg >= 0),
    CHECK (reps IS NOT NULL OR duration_seconds IS NOT NULL)
);
CREATE INDEX exercise_logs_workout ON exercise_logs(workout_log_id);
CREATE INDEX exercise_logs_exercise ON exercise_logs(exercise_id);

CREATE TABLE nutrition_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consumed_on TEXT NOT NULL,
    meal_name TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('manual', 'photo')),
    photo_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX nutrition_logs_calendar ON nutrition_logs(user_id, consumed_on);

CREATE TABLE nutrition_items (
    id INTEGER PRIMARY KEY,
    nutrition_log_id INTEGER NOT NULL REFERENCES nutrition_logs(id) ON DELETE CASCADE,
    food_name TEXT NOT NULL,
    serving_description TEXT NOT NULL,
    servings REAL NOT NULL CHECK (servings > 0),
    calories_per_serving REAL NOT NULL CHECK (calories_per_serving >= 0),
    protein_g_per_serving REAL CHECK (protein_g_per_serving >= 0),
    carbs_g_per_serving REAL CHECK (carbs_g_per_serving >= 0),
    fat_g_per_serving REAL CHECK (fat_g_per_serving >= 0),
    sodium_mg_per_serving REAL CHECK (sodium_mg_per_serving >= 0)
);
CREATE INDEX nutrition_items_log ON nutrition_items(nutrition_log_id);

CREATE TABLE progress_photos (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL, -- Private storage identifier, never a public static URL.
    taken_on TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX progress_photos_user_date ON progress_photos(user_id, taken_on);

CREATE TABLE goals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    metric TEXT NOT NULL CHECK (metric IN ('workouts', 'duration_minutes', 'load_kg', 'weight_kg', 'custom')),
    target_value REAL CHECK (target_value > 0),
    target_on TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX goals_user ON goals(user_id);

CREATE TABLE milestones (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    achieved_on TEXT NOT NULL
);
CREATE INDEX milestones_user_date ON milestones(user_id, achieved_on);

-- Completion is a deliberate transition, never implied by registration alone.
CREATE TRIGGER require_complete_onboarding
BEFORE UPDATE OF onboarding_completed_at ON users
WHEN NEW.onboarding_completed_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Onboarding requires a profile and preferences')
    WHERE NOT EXISTS (SELECT 1 FROM user_profiles WHERE user_id = NEW.id)
       OR NOT EXISTS (SELECT 1 FROM workout_preferences WHERE user_id = NEW.id);
END;
