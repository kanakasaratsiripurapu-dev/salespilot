-- SalesPilot schema (SQLite + PostgreSQL compatible)

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT PRIMARY KEY,
    account_name TEXT NOT NULL,
    industry TEXT,
    company_size INTEGER,
    revenue REAL,
    year_established INTEGER,
    region TEXT,
    subsidiary_of TEXT,
    latitude REAL,
    longitude REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    product_id BIGINT PRIMARY KEY,
    product_name TEXT NOT NULL UNIQUE,
    series TEXT,
    sales_price REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sales_teams (
    agent_id BIGINT PRIMARY KEY,
    sales_agent TEXT NOT NULL UNIQUE,
    manager TEXT,
    regional_office TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id BIGINT PRIMARY KEY,
    account_id BIGINT REFERENCES accounts(account_id),
    agent_id BIGINT REFERENCES sales_teams(agent_id),
    product_id BIGINT REFERENCES products(product_id),
    deal_value REAL,
    sales_stage TEXT,
    engage_date TEXT,
    close_date TEXT,
    days_since_last_contact INTEGER,
    deal_closed INTEGER CHECK (deal_closed IN (0, 1)),
    created_at TEXT DEFAULT (datetime('now'))
)
