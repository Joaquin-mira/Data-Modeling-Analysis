WITH bin_analysis AS (
    SELECT 
        LEFT(card_number, 6) AS bin,
        COUNT(DISTINCT card_number) AS unique_cards,
        COUNT(DISTINCT ip_address) AS unique_ips,
        COUNT(*) AS total_transactions,
        MIN(timestamp) AS first_seen,
        MAX(timestamp) AS last_seen,
        ROUND(EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 3600, 2) AS timespan_hours,
        ROUND(AVG(amount), 2) AS avg_amount,
        ROUND(SUM(amount), 2) AS total_amount,
        MODE() WITHIN GROUP (ORDER BY ip_address) AS most_common_ip
    FROM transactions
    WHERE amount <= 10
    GROUP BY LEFT(card_number, 6)
),

suspicious_bins AS (
    SELECT 
        *,
        ROUND(unique_cards::numeric / NULLIF(unique_ips, 0), 2) AS cards_per_ip,
        CASE
            WHEN unique_cards >= 100 AND unique_ips <= 3 THEN 'CRITICAL'
            WHEN unique_cards >= 50 AND unique_ips <= 5 THEN 'HIGH'
            WHEN unique_cards >= 30 AND unique_ips <= 10 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS threat_level
    FROM bin_analysis
    WHERE 
        unique_cards >= 30
        AND avg_amount <= 5
        AND unique_cards::numeric / NULLIF(unique_ips, 0) >= 10

)
SELECT
    bin as "BIN",
    unique_cards as "Unique cards",
    unique_ips as "Unique IPs",
    cards_per_ip as "Cards/IP",
    total_transactions as "Total transactions",
    avg_amount as "Avg. amount",
    total_amount as "Total amount",
    ROUND(timespan_hours, 1) as "Timespan (hrs)",
    threat_level as "Threat level",
    most_common_ip as "Most common IP",
    first_seen as "First seen",
    last_seen as "Last seen"
FROM suspicious_bins
WHERE threat_level IN ('CRITICAL', 'HIGH')
ORDER BY
    CASE threat_level
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        ELSE 4
    END,
    unique_cards DESC;