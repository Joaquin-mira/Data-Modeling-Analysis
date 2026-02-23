WITH ip_activity AS (
    SELECT
        ip_address,
        DATE_TRUNC('hour', timestamp) AS hour_bucket,
        FLOOR(EXTRACT(MINUTE FROM timestamp) / 5) AS five_min_windows,
        COUNT(DISTINCT card_number) AS unique_cards,
        COUNT(*) AS transaction_count,
        MIN(timestamp) as window_start,
        MAX(timestamp) as window_end,
        ROUND(EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 60, 2) AS duration_minutes,
        ROUND(AVG(amount), 2) AS avg_amount,
        ROUND(SUM(amount), 2) AS total_amount,

        ARRAY_AGG(DISTINCT LEFT(card_number, 6)) AS bins_used,
        ARRAY_AGG(DISTINCT LEFT (card_number, 10) ORDER BY LEFT(card_number, 10)) AS card_samples
    FROM transactions
    GROUP BY 
        ip_address,
        DATE_TRUNC('hour', timestamp),
        FLOOR(EXTRACT(MINUTE FROM timestamp) / 5)   
),
suspicious_ips AS (
    SELECT
        *,
        -- pattern filtering 
        CASE
            WHEN unique_cards >= 100 then 10
            WHEN unique_cards >= 50 THEN 9
            WHEN unique_cards >= 30 THEN 8
            WHEN unique_cards >= 20 THEN 7
            WHEN unique_cards >= 10 THEN 6
            ELSE 5
        END +
        CASE
            WHEN avg_amount >= 3 THEN 3
            WHEN avg_amount >= 5 THEN 2
            WHEN avg_amount >= 10 THEN 1
            ELSE 0
        END +
        CASE
            WHEN duration_minutes <= 5 THEN 3
            WHEN duration_minutes <= 10 THEN 2
            WHEN duration_minutes <= 15 THEN 1
            ELSE 0
        END AS risk_score
    FROM ip_activity
    WHERE 
        unique_cards >= 10 OR
        avg_amount >= 10 OR
        duration_minutes <= 30
)
SELECT
    ip_address,
    unique_cards as "Tested cards",
    transaction_count as "Transactions",
    duration_minutes as "Duration (min)",
    avg_amount as "Avg. amount",
    total_amount as "Total amount",
    bins_used as "BINs involved",
    risk_score as "Risk score",
    window_start as "Start",
    window_end as "End"
FROM suspicious_ips
WHERE risk_score >= 10 -- Adjusted on need
AND unique_cards >= 10
AND avg_amount <= 10 
ORDER BY risk_score DESC, unique_cards DESC;
