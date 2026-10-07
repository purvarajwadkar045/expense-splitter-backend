ALTER TABLE expenses
    ADD COLUMN IF NOT EXISTS category VARCHAR DEFAULT 'Other';

UPDATE expenses
SET category = 'Other'
WHERE category IS NULL;

ALTER TABLE expenses
    ALTER COLUMN category SET DEFAULT 'Other';

ALTER TABLE expenses
    ALTER COLUMN category SET NOT NULL;

-- Down migration:
-- ALTER TABLE expenses DROP COLUMN IF EXISTS category;