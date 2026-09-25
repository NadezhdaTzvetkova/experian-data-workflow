from __future__ import annotations

from typing import Any

import pandas as pd


def enrich_audit_flags(accepted: pd.DataFrame, vendors: pd.DataFrame, policy: dict[str, Any]) -> pd.DataFrame:
    enriched = accepted.merge(vendors, on="vendor_id", how="left", validate="many_to_one")
    enriched["transaction_date"] = pd.to_datetime(enriched["transaction_date"], errors="raise")
    enriched["effective_from"] = pd.to_datetime(enriched["effective_from"], errors="raise")
    enriched["effective_to"] = pd.to_datetime(enriched["effective_to"], errors="coerce")

    category_limits = {str(k): int(v) for k, v in policy["category_limits"].items()}
    enriched["policy_limit_minor"] = enriched["category"].map(category_limits).astype("Int64")
    enriched["policy_exception"] = enriched["policy_limit_minor"].notna() & enriched["amount_minor"].astype("int64").gt(enriched["policy_limit_minor"])
    enriched["high_risk_vendor"] = enriched["risk_rating"].eq("HIGH") if policy["vendor_controls"].get("flag_high_risk", False) else False
    inactive_by_end_date = enriched["effective_to"].notna() & enriched["transaction_date"].gt(enriched["effective_to"])
    inactive_by_flag = enriched["active_flag"].eq(0) & enriched["effective_to"].isna()
    enriched["inactive_vendor"] = (inactive_by_end_date | inactive_by_flag) if policy["vendor_controls"].get("flag_inactive", False) else False
    enriched["audit_exception"] = enriched[["policy_exception", "high_risk_vendor", "inactive_vendor"]].any(axis=1)

    return enriched
