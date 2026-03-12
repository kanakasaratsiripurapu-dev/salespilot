-- SalesPilot schema: accounts, products, sales_teams, opportunities

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT PRIMARY KEY,
    account_name TEXT NOT NULL,
    industry TEXT,
    company_size INTEGER,
    revenue DOUBLE PRECISION,
    year_established INTEGER,
    region TEXT,
    subsidiary_of TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_id BIGINT PRIMARY KEY,
    product_name TEXT NOT NULL UNIQUE,
    series TEXT,
    sales_price DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_teams (
    agent_id BIGINT PRIMARY KEY,
    sales_agent TEXT NOT NULL UNIQUE,
    manager TEXT,
    regional_office TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id BIGINT PRIMARY KEY,
    account_id BIGINT REFERENCES accounts(account_id),
    agent_id BIGINT REFERENCES sales_teams(agent_id),
    product_id BIGINT REFERENCES products(product_id),
    deal_value DOUBLE PRECISION,
    sales_stage TEXT,
    engage_date DATE,
    close_date DATE,
    days_since_last_contact INTEGER,
    deal_closed INTEGER CHECK (deal_closed IN (0, 1)),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opps_account_id ON opportunities(account_id);
CREATE INDEX IF NOT EXISTS idx_opps_agent_id ON opportunities(agent_id);
CREATE INDEX IF NOT EXISTS idx_opps_product_id ON opportunities(product_id);
CREATE INDEX IF NOT EXISTS idx_opps_sales_stage ON opportunities(sales_stage);
