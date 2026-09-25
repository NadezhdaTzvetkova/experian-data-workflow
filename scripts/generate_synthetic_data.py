from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SEED = 42
ROW_COUNT = 120
AS_OF_DATE = date(2026, 9, 1)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "source"
EXPENSES_PATH = SOURCE_DIR / "expenses.csv"
VENDORS_PATH = SOURCE_DIR / "vendors.db"
GROUND_TRUTH_PATH = SOURCE_DIR / "ground_truth.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_vendors() -> list[tuple[str, str, str, int, str, str | None]]:
    return [
        ("V001", "Vendor 001", "LOW", 1, "2025-01-01", None),
        ("V002", "Vendor 002", "LOW", 1, "2025-01-01", None),
        ("V003", "Vendor 003", "MEDIUM", 1, "2025-01-01", None),
        ("V004", "Vendor 004", "LOW", 1, "2025-01-01", None),
        ("V005", "Vendor 005", "HIGH", 1, "2025-01-01", None),
        ("V006", "Vendor 006", "LOW", 1, "2025-01-01", None),
        ("V007", "Vendor 007", "MEDIUM", 1, "2025-01-01", None),
        ("V008", "Vendor 008", "LOW", 0, "2025-01-01", "2026-06-30"),
        ("V009", "Vendor 009", "LOW", 1, "2025-01-01", None),
        ("V010", "Vendor 010", "HIGH", 1, "2025-01-01", None),
    ]


def generate_expenses() -> list[dict[str, object]]:
    rng = random.Random(SEED)
    categories = ["travel", "meals", "accommodation", "office"]
    vendors = [f"V{i:03d}" for i in range(1, 11)]
    rows: list[dict[str, object]] = []
    for index in range(ROW_COUNT):
        transaction_date = AS_OF_DATE - timedelta(days=rng.randint(1, 180))
        category = rng.choice(categories)
        amount_minor = rng.randint(1500, 85000)
        rows.append({
            "transaction_id": f"TX{index + 1:04d}",
            "employee_id": f"EMP{rng.randint(1, 20):03d}",
            "vendor_id": rng.choice(vendors),
            "transaction_date": transaction_date.isoformat(),
            "category": category,
            "currency": "EUR",
            "amount_minor": amount_minor,
            "cost_center": rng.choice(["CC_FINANCE", "CC_TECH", "CC_SALES", "CC_HR"]),
            "receipt_present": rng.choice([True, True, True, False]),
        })
    rows[110]["category"], rows[110]["amount_minor"] = "travel", 135000
    rows[111]["category"], rows[111]["amount_minor"] = "meals", 14500
    rows[112]["category"], rows[112]["amount_minor"] = "accommodation", 68000
    rows[113]["vendor_id"] = "V005"
    rows[114]["vendor_id"] = "V008"
    rows[114]["transaction_date"] = "2026-07-15"
    rows[115]["transaction_id"] = rows[0]["transaction_id"]
    rows[116]["transaction_id"] = ""
    rows[117]["amount_minor"] = -2500
    rows[118]["transaction_date"] = "2026-09-05"
    rows[119]["vendor_id"] = "V999"
    return rows


def write_expenses(rows: list[dict[str, object]]) -> None:
    fieldnames = ["transaction_id", "employee_id", "vendor_id", "transaction_date", "category", "currency", "amount_minor", "cost_center", "receipt_present"]
    with EXPENSES_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_vendors(vendors: list[tuple[str, str, str, int, str, str | None]]) -> None:
    if VENDORS_PATH.exists():
        VENDORS_PATH.unlink()
    with sqlite3.connect(VENDORS_PATH) as connection:
        connection.execute("CREATE TABLE vendors (vendor_id TEXT PRIMARY KEY, vendor_name TEXT NOT NULL, risk_rating TEXT NOT NULL, active_flag INTEGER NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT)")
        connection.executemany("INSERT INTO vendors VALUES (?, ?, ?, ?, ?, ?)", vendors)
        connection.commit()


def write_ground_truth() -> None:
    payload = {
        "seed": SEED,
        "source_rows": ROW_COUNT,
        "oracle_usage": "test_and_review_only_not_production_validation",
        "injected_data_defects": {
            "duplicate_transaction_id": 1,
            "missing_transaction_id": 1,
            "invalid_amount": 1,
            "future_transaction_date": 1,
            "unknown_vendor": 1,
        },
        "injected_valid_audit_examples": {
            "policy_limit_breach_transaction_ids": ["TX0111", "TX0112", "TX0113"],
            "high_risk_vendor_transaction_ids": ["TX0114"],
            "inactive_vendor_transaction_ids": ["TX0115"],
        },
    }
    GROUND_TRUTH_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    rows = generate_expenses()
    write_expenses(rows)
    write_vendors(build_vendors())
    write_ground_truth()
    print(f"seed={SEED}")
    print(f"expenses_rows={len(rows)}")
    print(f"expenses_sha256={sha256(EXPENSES_PATH)}")
    print(f"vendors_sha256={sha256(VENDORS_PATH)}")
    print(f"ground_truth_sha256={sha256(GROUND_TRUTH_PATH)}")


if __name__ == "__main__":
    main()


