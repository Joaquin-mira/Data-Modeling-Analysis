WITH transaction_velocity AS (
    SELECT
        ip_address,
        timestamp,
        card_number,
        amount,
        LEFT(card_number, 6) AS bin,
        LAG(timestamp) OVER (PARTITION BY ip_address ORDER BY timestamp) AS prev_timestamp,
        LAG(card_number) OVER (PARTITION BY ip_address ORDER BY timestamp) as prev_card,
        LAG(amount) OVER (PARTITION BY ip_address ORDER BY timestamp) as prev_amount,

        EXTRACT(EPOCH FROM (
            timestamp - LAG(timestamp) OVER (PARTITION BY ip_address ORDER BY timestamp)
        )) AS seconds_since_last
    FROM transactions
    WHERE amount <= 10
),

rapid_fire_events AS (
    SELECT 
        ip_address,
        timestamp,
        card_number,
        amount,
        bin,
        prev_card,
        seconds_since_last,

        CASE
            WHEN seconds_since_last <= 5 THEN 'INSTANT (<5s)'
            WHEN seconds_since_last <= 10 THEN 'VERY FAST (<10s)'
            WHEN seconds_since_last <= 30 THEN 'FAST (<30s)'
            ELSE 'NORMAL'
        END AS velocity_class
    FROM transaction_velocity
    WHERE
        seconds_since_last IS NOT NULL
        AND seconds_since_last <= 30
        AND card_number != prev_card
),

ip_rapid_summary AS (
    SELECT
        ip_address,
        COUNT(*) AS rapid_fire_count,
        COUNT(DISTINCT card_number) AS unique_cards_rapid,
        COUNT(DISTINCT bin) AS unique_bins,
        ROUND(AVG(seconds_since_last), 2) AS avg_gap_seconds,
        MIN(seconds_since_last) AS fastest_gap,
        ROUND(AVG(amount), 2) AS avg_mount,
        MIN(timestamp) as first_rapid_txn,
        MAX(timestamp) as last_rapid_txn
    FROM rapid_fire_events
    GROUP BY ip_address
)
SELECT
    ip_address as "IP Address",
    rapid_fire_count as "Rapid-fire transactions",
    unique_cards_rapid as "Unique cards",
    unique_bins as "Unique bins",
    avg_gap_seconds as "Avg. gap (s)",
    fastest_gap as "Fastest gap (s)",
    avg_mount as "Avg. amount",
    first_rapid_txn as "Start",
    last_rapid_txn as "End",
    CASE
        WHEN rapid_fire_count >= 50 AND avg_gap_seconds <= 10 THEN 'CRITICAL'
        WHEN rapid_fire_count >= 30 AND avg_gap_seconds <= 15 THEN 'HIGH'
        WHEN rapid_fire_count >= 20 AND avg_gap_seconds <= 20 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level
FROM ip_rapid_summary
WHERE rapid_fire_count >= 10
ORDER BY
    rapid_fire_count DESC, avg_gap_seconds ASC;