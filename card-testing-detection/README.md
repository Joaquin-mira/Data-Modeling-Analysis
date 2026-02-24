# 💳 Card Testing Fraud Detection

A fraud detection system that simulates card testing attacks against a payment processing database, then uses SQL analytical queries to detect them through three complementary detection layers: velocity analysis, rapid-fire detection, and BIN pattern analysis.

Built with Python (data generation + PostgreSQL ingestion) and pure SQL (detection queries using CTEs, window functions, and pattern scoring).

---

## Table of Contents

- [Overview](#overview)
- [What is Card Testing?](#what-is-card-testing)
- [Detection Layers](#detection-layers)
- [Project Structure](#project-structure)
- [How to Run](#how-to-run)
- [Results](#results)
- [Tech Stack](#tech-stack)

---

## Overview

The system generates ~10,400 credit card transactions: 9,999 legitimate and ~400 fraudulent across 3 simulated card testing attacks. All data is loaded into PostgreSQL, where three SQL detection queries analyze the transactions from different angles.

**Pipeline:**

1. **Schema Setup** (`schema.sql`) — Creates the `transactions` table with indexes optimized for fraud detection queries.
2. **Data Generation** (`cardTestingMotor.py`) — Generates realistic legitimate transactions and injects 3 card testing attacks with configurable parameters. Loads everything into PostgreSQL.
3. **Detection Queries** — Three SQL scripts that analyze the data from complementary angles:
   - `velocityAnalysis.sql` — 5-minute window velocity analysis
   - `rapidFireDetection.sql` — Sub-30-second rapid-fire pattern detection
   - `binDetection.sql` — BIN-level concentration analysis

---

## What is Card Testing?

Card testing is a fraud scheme where an attacker obtains a batch of stolen card numbers (usually sharing the same BIN prefix) and tests them by making small transactions ($1–$5) in rapid succession to identify which cards are still active. Once validated, the working cards are used for larger fraudulent purchases or sold on dark web marketplaces.

**Key behavioral signatures:**

- Many unique card numbers from the same BIN prefix in a short time window
- Very small transaction amounts (micro-payments to minimize detection)
- High velocity: multiple transactions per minute from the same IP
- Few IP addresses testing many cards (1–3 IPs per attack)

---

## Detection Layers

### Layer 1: Velocity Analysis (`velocityAnalysis.sql`)

Groups transactions into 5-minute windows per IP and calculates a composite risk score based on three factors: number of unique cards tested, average transaction amount, and window duration.

**SQL Techniques:**
- `DATE_TRUNC()` + `FLOOR(EXTRACT(MINUTE) / 5)` for 5-minute bucketing
- `ARRAY_AGG(DISTINCT ...)` to collect BINs and card samples per window
- Composite scoring with weighted CASE expressions

**Sample output:**

| IP Address | Tested Cards | Duration (min) | Avg Amount | Risk Score |
|---|---|---|---|---|
| 76.135.93.236 | 25 | 3.12 | $3.04 | 13 |
| 231.190.185.231 | 20 | 4.72 | $3.26 | 13 |
| 162.142.97.239 | 20 | 4.30 | $3.00 | 13 |

### Layer 2: Rapid-Fire Detection (`rapidFireDetection.sql`)

Uses `LAG()` window functions to calculate the time gap between consecutive transactions from the same IP. Flags IPs with sustained bursts of card-switching transactions under 30 seconds apart.

**SQL Techniques:**
- `LAG()` over `PARTITION BY ip_address ORDER BY timestamp` for inter-transaction gap calculation
- `EXTRACT(EPOCH FROM ...)` for time difference in seconds
- Velocity classification: INSTANT (<5s), VERY FAST (<10s), FAST (<30s)

**Sample output:**

| IP Address | Rapid-fire Txns | Unique Cards | Avg Gap (s) | Risk Level |
|---|---|---|---|---|
| 76.135.93.236 | 149 | 149 | 6.01 | CRITICAL |
| 2.72.35.164 | 52 | 52 | 10.15 | HIGH |
| 231.190.185.231 | 51 | 51 | 10.35 | HIGH |

### Layer 3: BIN Concentration Analysis (`binDetection.sql`)

Aggregates at the BIN level to detect when many unique cards from the same issuer are being tested in a short timespan with low amounts, indicating a compromised batch.

**SQL Techniques:**
- `MODE() WITHIN GROUP (ORDER BY ...)` for most common IP per BIN
- Cards-per-IP ratio as concentration metric
- Threat classification based on unique card count and IP dispersion

**Sample output:**

| BIN | Unique Cards | Unique IPs | Cards/IP | Timespan (hrs) | Threat Level |
|---|---|---|---|---|---|
| 454172 | 150 | 1 | 150.00 | 0.3 | CRITICAL |
| 923157 | 149 | 3 | 49.67 | 0.3 | CRITICAL |
| 184637 | 104 | 2 | 52.00 | 0.2 | CRITICAL |

### Why Three Layers?

Each layer catches what the others might miss. Velocity analysis detects concentrated bursts within time windows. Rapid-fire detection catches the transaction-by-transaction speed pattern. BIN analysis reveals the structural signature of a compromised card batch. An IP that appears in all three layers is a confirmed attack with high confidence.

---

## Project Structure

```
card-testing-detection/
├── README.md
├── requirements.txt
├── schema.sql                  # Database schema + indexes
├── cardTestingMotor.py         # Data generation + PostgreSQL ingestion
├── sql/
│   ├── velocityAnalysis.sql    # Layer 1: 5-min window analysis
│   ├── rapidFireDetection.sql  # Layer 2: Sub-30s rapid-fire detection
│   └── binDetection.sql        # Layer 3: BIN concentration analysis
└── sample-output/
    ├── velocityOutput.txt      # Sample results from Layer 1
    ├── rapidFireOutput.txt     # Sample results from Layer 2
    └── binOutput.txt           # Sample results from Layer 3
```

---

## How to Run

### Prerequisites

- Python 3.9+
- PostgreSQL 14+
- pip

### Installation

```bash
cd Data-Modeling-Analysis/card-testing-detection
pip install -r requirements.txt
```

### Setup

1. **Create the database and schema:**

```bash
psql -U postgres -c "CREATE DATABASE card_db;"
psql -U postgres -d card_db -f schema.sql
```

2. **Configure database credentials** via environment variables:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=card_db
export DB_USER=postgres
export DB_PASSWORD=your_password
```

3. **Generate and load data:**

```bash
python cardTestingMotor.py
```

4. **Run detection queries:**

```bash
psql -U postgres -d card_db -f sql/velocityAnalysis.sql
psql -U postgres -d card_db -f sql/rapidFireDetection.sql
psql -U postgres -d card_db -f sql/binDetection.sql
```

---

## Results

### Attack Detection Summary

All 3 injected card testing attacks were detected by all 3 detection layers:

| Attack | BIN | Cards Tested | IPs Used | Detected By |
|---|---|---|---|---|
| Attack 1 | 454172 | 150 | 1 | All 3 layers (CRITICAL) |
| Attack 2 | 923157 | 149 | 3 | All 3 layers (CRITICAL) |
| Attack 3 | 184637 | 104 | 2 | All 3 layers (CRITICAL) |

### Key Takeaways

- **Pure SQL is powerful for fraud detection.** CTEs, window functions, and CASE expressions provide a complete detection framework without needing Python ML libraries.
- **Layered detection reduces false positives.** A legitimate merchant processing many cards would not trigger rapid-fire detection, and a legitimate burst of transactions would not show BIN concentration.
- **The attacker's constraint is their advantage for detection.** Card testing requires speed (to test before cards are blocked) and volume (to find working cards), both of which create detectable statistical signatures.

---

## Tech Stack

| Tool | Usage |
|---|---|
| **Python** | Synthetic data generation, PostgreSQL ingestion |
| **PostgreSQL** | Transaction storage, analytical queries |
| **SQL (CTEs)** | Multi-stage detection pipeline |
| **SQL (Window Functions)** | LAG(), PARTITION BY for inter-transaction analysis |
| **psycopg2** | Python-PostgreSQL adapter with bulk insert |
