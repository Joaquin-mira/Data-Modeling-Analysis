

DROP TABLE IF EXISTS transactions;

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    card_number VARCHAR(16) NOT NULL,
    bin VARCHAR(6) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    customer_id VARCHAR(50),
    is_fraud BOOLEAN DEFAULT FALSE,
    fraud_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON transactions(timestamp);
CREATE INDEX idx_ip_bin ON transactions(ip_address, bin);
CREATE INDEX idx_amount ON transactions(amount);
CREATE INDEX idx_is_fraud ON transactions(is_fraud);


SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) as fraud_count,
    MIN(timestamp) as earliest,
    MAX(timestamp) as latest
FROM transactions;