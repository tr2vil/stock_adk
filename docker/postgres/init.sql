-- Initial schema for stock trading system
CREATE TABLE IF NOT EXISTS economic_indicators (
    id SERIAL PRIMARY KEY,
    indicator_name VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    value NUMERIC NOT NULL,
    UNIQUE(indicator_name, recorded_at)
);

CREATE TABLE IF NOT EXISTS stocks (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sector VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) REFERENCES stocks(symbol),
    recorded_at TIMESTAMP NOT NULL,
    price_close NUMERIC NOT NULL,
    volume BIGINT,
    UNIQUE(symbol, recorded_at)
);
