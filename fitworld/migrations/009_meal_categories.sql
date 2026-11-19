-- Existing meals remain explicitly uncategorized; do not guess from their names.
ALTER TABLE nutrition_logs ADD COLUMN meal_category TEXT NOT NULL DEFAULT 'uncategorized'
    CHECK (meal_category IN ('uncategorized', 'breakfast', 'lunch', 'dinner', 'snack'));
ALTER TABLE favorite_meals ADD COLUMN meal_category TEXT NOT NULL DEFAULT 'uncategorized'
    CHECK (meal_category IN ('uncategorized', 'breakfast', 'lunch', 'dinner', 'snack'));
