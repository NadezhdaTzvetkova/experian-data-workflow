SELECT
    category,
    CAST(COUNT(*) AS BIGINT) AS transaction_count,
    CAST(SUM(amount_minor) AS BIGINT) AS spend_minor,
    CAST(SUM(CASE WHEN policy_exception THEN 1 ELSE 0 END) AS BIGINT) AS policy_exception_count,
    CAST(SUM(CASE WHEN high_risk_vendor THEN 1 ELSE 0 END) AS BIGINT) AS high_risk_vendor_count,
    CAST(SUM(CASE WHEN inactive_vendor THEN 1 ELSE 0 END) AS BIGINT) AS inactive_vendor_count,
    CAST(SUM(CASE WHEN audit_exception THEN 1 ELSE 0 END) AS BIGINT) AS audit_exception_count
FROM read_parquet(?)
GROUP BY category
ORDER BY spend_minor DESC, category ASC;
