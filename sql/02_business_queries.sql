-- =====================================================================
-- PhonePe Transaction Insights : business-case SQL (PostgreSQL)
-- Each block starts with "-- name: <id>" and is executed + exported by
-- sql/run_queries.py. Amounts are in INR; "cr" = crore (10^7 INR).
--
-- Conventions
--   * "latest" is derived from the data (no hard-coded dates).
--   * Full calendar years only (<= 2025) are used for YoY / CAGR, because
--     2026 currently holds just Q1-Q2.
--   * Amounts exist only in map_transaction (district level).
-- =====================================================================


-- name: q01_yearly_category_growth
-- USE CASE: Payment Performance. Volume and YoY growth per payment category.
WITH yearly AS (
    SELECT year, payment_category, SUM(txn_count) AS txns
    FROM aggregated_transaction
    WHERE year <= 2025
    GROUP BY year, payment_category
)
SELECT year, payment_category, txns,
       ROUND(100.0 * (txns - LAG(txns) OVER w) / NULLIF(LAG(txns) OVER w, 0), 1) AS yoy_pct
FROM yearly
WINDOW w AS (PARTITION BY payment_category ORDER BY year)
ORDER BY year, payment_category;


-- name: q02_top_states_all_time
-- USE CASE: Geographical Insights. Top 10 states by lifetime transactions.
SELECT RANK() OVER (ORDER BY SUM(txn_count) DESC) AS rank,
       state,
       SUM(txn_count)                               AS total_txns,
       ROUND(100.0 * SUM(txn_count) / SUM(SUM(txn_count)) OVER (), 2) AS share_pct
FROM aggregated_transaction
GROUP BY state
ORDER BY total_txns DESC
LIMIT 10;


-- name: q03_top_districts_by_amount_2025
-- USE CASE: Geographical Insights / Marketing Optimization. Top 15 districts by 2025 value.
SELECT district, state,
       SUM(txn_count)                                   AS txns,
       ROUND(SUM(txn_amount) / 1e7)                     AS amount_cr,
       ROUND(SUM(txn_amount) / NULLIF(SUM(txn_count),0), 0) AS avg_ticket_inr
FROM map_transaction
WHERE year = 2025
GROUP BY district, state
ORDER BY SUM(txn_amount) DESC
LIMIT 15;


-- name: q04_state_ticket_size_2025
-- USE CASE: Customer Segmentation. Average ticket size by state vs national (=100).
WITH s AS (
    SELECT state, SUM(txn_count) AS txns, SUM(txn_amount) AS amount
    FROM map_transaction WHERE year = 2025 GROUP BY state
), nat AS (
    SELECT SUM(amount) / SUM(txns) AS nat_ticket FROM s
)
SELECT s.state, s.txns, ROUND(s.amount / 1e7) AS amount_cr,
       ROUND(s.amount / s.txns, 0)                       AS avg_ticket_inr,
       ROUND(100 * (s.amount / s.txns) / nat.nat_ticket) AS ticket_index
FROM s CROSS JOIN nat
ORDER BY avg_ticket_inr DESC;


-- name: q05_quarterly_trend_qoq
-- USE CASE: Trend Analysis. National quarterly volume, value and QoQ growth.
WITH q AS (
    SELECT year, quarter,
           SUM(txn_count)        AS txns,
           SUM(txn_amount) / 1e7 AS amount_cr
    FROM map_transaction
    GROUP BY year, quarter
)
SELECT year, quarter, txns, ROUND(amount_cr) AS amount_cr,
       ROUND(100.0 * (txns - LAG(txns) OVER o) / NULLIF(LAG(txns) OVER o, 0), 1) AS qoq_txn_pct
FROM q
WINDOW o AS (ORDER BY year, quarter)
ORDER BY year, quarter;


-- name: q06_engagement_by_state_latest
-- USE CASE: User Engagement. Transactions per registered user, latest quarter.
WITH latest AS (
    SELECT year, quarter FROM aggregated_user ORDER BY year DESC, quarter DESC LIMIT 1
), t AS (
    SELECT a.state, SUM(a.txn_count) AS txns
    FROM aggregated_transaction a JOIN latest l USING (year, quarter)
    GROUP BY a.state
), e AS (
    SELECT t.state, u.registered_users, t.txns,
           t.txns::numeric / u.registered_users AS txns_per_user
    FROM t
    JOIN aggregated_user u ON u.state = t.state
    JOIN latest l ON u.year = l.year AND u.quarter = l.quarter
)
SELECT state, registered_users, txns,
       ROUND(txns_per_user, 2)                                          AS txns_per_user,
       ROUND(100 * txns_per_user / (SUM(txns) OVER () / SUM(registered_users) OVER ()::numeric)) AS engagement_index,
       RANK() OVER (ORDER BY txns_per_user DESC)                        AS rank
FROM e
ORDER BY txns_per_user DESC;


-- name: q07_district_segments_2025
-- USE CASE: Customer Segmentation. Districts split by frequency x ticket size (median cut).
WITH d AS (
    SELECT t.state, t.district,
           SUM(t.txn_count) AS txns, SUM(t.txn_amount) AS amount,
           MAX(u.registered_users) AS users
    FROM map_transaction t
    JOIN map_user u ON u.state = t.state AND u.district = t.district
                   AND u.year = 2025 AND u.quarter = 4
    WHERE t.year = 2025
    GROUP BY t.state, t.district
    HAVING MAX(u.registered_users) > 0
), m AS (
    SELECT *, txns::numeric / users AS freq, amount / txns AS ticket FROM d
), cut AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY freq)   AS f_med,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ticket) AS t_med
    FROM m
), seg AS (
    SELECT m.*, CASE
        WHEN freq >= f_med AND ticket >= t_med THEN 'Power hubs (frequent, high ticket)'
        WHEN freq >= f_med AND ticket <  t_med THEN 'Everyday spenders (frequent, low ticket)'
        WHEN freq <  f_med AND ticket >= t_med THEN 'Big-ticket occasional'
        ELSE 'Emerging / under-engaged' END AS segment
    FROM m CROSS JOIN cut
)
SELECT segment,
       COUNT(*)                                  AS districts,
       ROUND(SUM(users) / 1e6, 1)                AS users_mn,
       ROUND(AVG(freq), 1)                       AS avg_txns_per_user,
       ROUND(AVG(ticket), 0)                     AS avg_ticket_inr,
       ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 1) AS value_share_pct
FROM seg
GROUP BY segment
ORDER BY value_share_pct DESC;


-- name: q08_ticket_size_anomalies
-- USE CASE: Fraud Detection (screening). District-quarters whose average ticket is
-- >3 standard deviations above the national district distribution for that quarter.
-- This FLAGS unusual patterns for review; it does not prove fraud.
WITH dq AS (
    SELECT state, district, year, quarter, txn_count,
           txn_amount / NULLIF(txn_count, 0) AS ticket
    FROM map_transaction
    WHERE txn_count >= 10000                       -- ignore tiny samples
      AND (year, quarter) IN (SELECT year, quarter FROM map_transaction
                              GROUP BY year, quarter ORDER BY year DESC, quarter DESC LIMIT 4)
), z AS (
    SELECT *, (ticket - AVG(ticket) OVER w) / NULLIF(STDDEV_POP(ticket) OVER w, 0) AS z_score
    FROM dq WINDOW w AS (PARTITION BY year, quarter)
)
SELECT state, district, year, quarter, txn_count,
       ROUND(ticket, 0) AS avg_ticket_inr, ROUND(z_score, 2) AS z_score
FROM z
WHERE z_score > 3
ORDER BY z_score DESC
LIMIT 20;


-- name: q09_state_cagr_2022_2025
-- USE CASE: Trend Analysis / Marketing Optimization. 3-year transaction CAGR by state.
WITH y AS (
    SELECT state,
           SUM(txn_count) FILTER (WHERE year = 2022) AS t22,
           SUM(txn_count) FILTER (WHERE year = 2025) AS t25
    FROM aggregated_transaction GROUP BY state
)
SELECT state, t22 AS txns_2022, t25 AS txns_2025,
       ROUND(100 * (POWER(t25::numeric / t22, 1.0 / 3) - 1), 1) AS cagr_pct,
       RANK() OVER (ORDER BY t25::numeric / t22 DESC)           AS rank
FROM y
WHERE t22 > 0
ORDER BY cagr_pct DESC;


-- name: q10_category_mix_by_state_2025
-- USE CASE: Payment Performance. Share of P2P / Retail / Utility by state.
SELECT state,
       ROUND(100.0 * SUM(txn_count) FILTER (WHERE payment_category = 'P2P')     / SUM(txn_count), 1) AS p2p_pct,
       ROUND(100.0 * SUM(txn_count) FILTER (WHERE payment_category = 'Retail')  / SUM(txn_count), 1) AS retail_pct,
       ROUND(100.0 * SUM(txn_count) FILTER (WHERE payment_category = 'Utility') / SUM(txn_count), 1) AS utility_pct,
       SUM(txn_count) AS txns
FROM aggregated_transaction
WHERE year = 2025
GROUP BY state
ORDER BY retail_pct DESC;


-- name: q11_seasonality_by_quarter
-- USE CASE: Trend Analysis. Average QoQ growth by calendar quarter (2019-2025).
WITH q AS (
    SELECT year, quarter, SUM(txn_count) AS txns
    FROM aggregated_transaction GROUP BY year, quarter
), g AS (
    SELECT year, quarter,
           100.0 * (txns - LAG(txns) OVER (ORDER BY year, quarter))
                 / LAG(txns) OVER (ORDER BY year, quarter) AS qoq
    FROM q
)
SELECT quarter, ROUND(AVG(qoq), 1) AS avg_qoq_pct, COUNT(*) AS years_observed
FROM g
WHERE year BETWEEN 2019 AND 2025
GROUP BY quarter
ORDER BY quarter;


-- name: q12_merchant_penetration_latest
-- USE CASE: Product Development. Merchants per 1,000 users and YoY merchant growth.
WITH latest AS (
    SELECT year, quarter FROM aggregated_merchant ORDER BY year DESC, quarter DESC LIMIT 1
)
SELECT m.state, m.registered_merchants, u.registered_users,
       ROUND(1000.0 * m.registered_merchants / u.registered_users, 1) AS merchants_per_1k_users,
       ROUND(100.0 * (m.registered_merchants - p.registered_merchants)
                   / NULLIF(p.registered_merchants, 0), 1)            AS merchant_yoy_pct
FROM aggregated_merchant m
JOIN latest l ON m.year = l.year AND m.quarter = l.quarter
JOIN aggregated_user u ON u.state = m.state AND u.year = m.year AND u.quarter = m.quarter
LEFT JOIN aggregated_merchant p ON p.state = m.state AND p.year = m.year - 1 AND p.quarter = m.quarter
ORDER BY merchants_per_1k_users DESC;


-- name: q13_untapped_districts_2025
-- USE CASE: Marketing Optimization. Large user base but bottom-quartile activity per user.
WITH d AS (
    SELECT t.state, t.district, SUM(t.txn_count) AS txns, MAX(u.registered_users) AS users
    FROM map_transaction t
    JOIN map_user u ON u.state = t.state AND u.district = t.district
                   AND u.year = 2025 AND u.quarter = 4
    WHERE t.year = 2025
    GROUP BY t.state, t.district
    HAVING MAX(u.registered_users) > 0
), r AS (
    SELECT *, txns::numeric / users AS freq,
           NTILE(4) OVER (ORDER BY txns::numeric / users) AS freq_quartile,
           PERCENT_RANK() OVER (ORDER BY users)            AS size_pct
    FROM d
)
SELECT state, district, users AS registered_users, txns, ROUND(freq, 1) AS txns_per_user
FROM r
WHERE freq_quartile = 1 AND size_pct >= 0.5
ORDER BY users DESC
LIMIT 15;


-- name: q14_top_district_per_state_latest
-- USE CASE: Geographical Insights. #1 district of every state (top_transaction), latest quarter.
WITH latest AS (
    SELECT year, quarter FROM top_transaction ORDER BY year DESC, quarter DESC LIMIT 1
)
SELECT t.state, t.entity_name AS top_district, t.txn_count,
       ROUND(100.0 * t.txn_count / a.total, 1) AS share_of_state_pct
FROM top_transaction t
JOIN latest l ON t.year = l.year AND t.quarter = l.quarter
JOIN (SELECT state, year, quarter, SUM(txn_count) AS total
      FROM aggregated_transaction GROUP BY state, year, quarter) a
  ON a.state = t.state AND a.year = t.year AND a.quarter = t.quarter
WHERE t.entity_level = 'district' AND t.rank = 1
ORDER BY share_of_state_pct DESC;


-- name: q15_users_merchants_year_end
-- USE CASE: User Engagement. National registered users & merchants at each year's last quarter.
WITH last_q AS (
    SELECT year, MAX(quarter) AS quarter FROM aggregated_user GROUP BY year
), n AS (
    SELECT l.year, l.quarter,
           (SELECT SUM(registered_users)     FROM aggregated_user     u WHERE u.year = l.year AND u.quarter = l.quarter) AS users,
           (SELECT SUM(registered_merchants) FROM aggregated_merchant m WHERE m.year = l.year AND m.quarter = l.quarter) AS merchants
    FROM last_q l
)
SELECT year, quarter AS as_of_quarter, users, merchants,
       ROUND(100.0 * (users - LAG(users) OVER (ORDER BY year)) / NULLIF(LAG(users) OVER (ORDER BY year), 0), 1) AS growth_vs_prev_row_pct   -- NB: 2026 row is a half-year point vs end-2025
FROM n
ORDER BY year;


-- name: q16_state_period_metrics
-- DASHBOARD FEED. One row per state x quarter with every headline metric.
WITH tx AS (
    SELECT state, year, quarter,
           SUM(txn_count)  AS txns,
           SUM(txn_count) FILTER (WHERE payment_category = 'P2P')     AS p2p,
           SUM(txn_count) FILTER (WHERE payment_category = 'Retail')  AS retail,
           SUM(txn_count) FILTER (WHERE payment_category = 'Utility') AS utility
    FROM aggregated_transaction GROUP BY state, year, quarter
), amt AS (
    SELECT state, year, quarter, ROUND(SUM(txn_amount) / 1e7) AS amount_cr
    FROM map_transaction GROUP BY state, year, quarter
)
SELECT tx.state, tx.year, tx.quarter, tx.txns, amt.amount_cr,
       u.registered_users AS users, m.registered_merchants AS merchants,
       tx.p2p, tx.retail, tx.utility
FROM tx
LEFT JOIN amt USING (state, year, quarter)
LEFT JOIN aggregated_user     u USING (state, year, quarter)
LEFT JOIN aggregated_merchant m USING (state, year, quarter)
ORDER BY tx.year, tx.quarter, tx.state;


-- name: q17_district_yearly
-- DASHBOARD FEED. District totals per calendar year (drill-down charts).
SELECT state, district, year,
       SUM(txn_count)                AS txns,
       ROUND(SUM(txn_amount) / 1e7)  AS amount_cr
FROM map_transaction
GROUP BY state, district, year
ORDER BY year, state, district;
