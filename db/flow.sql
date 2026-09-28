CREATE TABLE candles (
    symbol VARCHAR(20) NOT NULL, 
    timestamp TIMESTAMPTZ NOT NULL,

    open NUMERIC(12, 2) NOT NULL,
    high NUMERIC(12, 2) NOT NULL,
    low NUMERIC(12, 2) NOT NULL,
    close NUMERIC(12, 2) NOT NULL,
    volume BIGINT NOT NULL,

    PRIMARY KEY (symbol, timestamp)
);