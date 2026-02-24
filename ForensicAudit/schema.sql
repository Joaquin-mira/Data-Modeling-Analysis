DROP TABLE IF EXISTS transactions;

CREATE TABLE transactions (
    transaction_id  INT PRIMARY KEY,
    date            DATE NOT NULL,
    employee_id     VARCHAR(10) NOT NULL,
    vendor_id       VARCHAR(10) NOT NULL,
    amount          DECIMAL(10, 2) NOT NULL,
    category        VARCHAR(50) NOT NULL,
    invoice_number  VARCHAR(50) NOT NULL
);

CREATE INDEX idx_txn_employee ON transactions(employee_id);
CREATE INDEX idx_txn_vendor ON transactions(vendor_id);
CREATE INDEX idx_txn_date ON transactions(date);
CREATE INDEX idx_txn_invoice ON transactions(invoice_number);
CREATE INDEX idx_txn_emp_vendor_date ON transactions(employee_id, vendor_id, date);