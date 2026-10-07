CREATE TABLE IF NOT EXISTS budgets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    budget_month VARCHAR(7) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT _user_budget_month_uc UNIQUE (user_id, budget_month)
);

CREATE INDEX IF NOT EXISTS ix_budgets_user_id ON budgets (user_id);

-- Down migration:
-- DROP TABLE IF EXISTS budgets;