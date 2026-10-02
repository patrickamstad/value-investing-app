##################################################################################################
"""YOU NEED TO RUN THIS FILE FROM THE FOLDER IT IS IN; OTHERWISE IMPORTS WILL FAIL"""
##################################################################################################

import argparse
import os
import json
import logging
import psycopg2
import pandas as pd
import boto3
from botocore.config import Config
from datetime import date as _date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

from migration_utils import (
    create_temp_staging_table,
    bulk_insert_staging,
    insert_from_staging,
    CONFLICT_COLUMNS,
    get_db_connection,
)
from eodhd_field_mappings import (
    transform_traded_company,
    transform_income_statement,
    transform_balance_sheet,
    transform_cash_flow,
)

load_dotenv()
load_dotenv(Path(__file__).parent / ".env.local", override=True)  # local overrides (e.g. DB_HOST/DB_PORT for debugging outside Docker)

# ── Migration flags ────────────────────────────────────────────────────────────
MIGRATE_INCOME_STATEMENT_DATA = True
MIGRATE_BALANCE_SHEET_DATA    = True
MIGRATE_CF_STATEMENT_DATA     = True

# ── Config ─────────────────────────────────────────────────────────────────────
BATCH_SIZE   = 500   # flush to DB after accumulating this many companies
S3_WORKERS   = 3    # parallel threads for S3 downloads + JSON parsing
S3_BUCKET    = os.environ["S3_BUCKET_NAME"]
S3_PREFIX_HISTORICAL = "eodhd-fundamentals"
S3_PREFIX_BULK       = "eodhd-fundamentals-bulk"

# ── Logging ────────────────────────────────────────────────────────────────────
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    filename=log_dir / "main.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger().addHandler(logging.StreamHandler())

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    config=Config(max_pool_connections=S3_WORKERS),
)

# ── Table registry ─────────────────────────────────────────────────────────────
# (staging_name, target_table, enabled)
def _build_registry() -> dict:
    return {
        "companies":      ("stag_traded_companies",  "quickfs_dj_tradedcompanies",          True),
        "income_annual":  ("stag_income_annual",      "quickfs_dj_incomestatementannual",    MIGRATE_INCOME_STATEMENT_DATA),
        "income_quarter": ("stag_income_quarter",     "quickfs_dj_incomestatementquarter",   MIGRATE_INCOME_STATEMENT_DATA),
        "balance_annual": ("stag_balance_annual",     "quickfs_dj_balancesheetannual",       MIGRATE_BALANCE_SHEET_DATA),
        "balance_quarter":("stag_balance_quarter",    "quickfs_dj_balancesheetquarter",      MIGRATE_BALANCE_SHEET_DATA),
        "cf_annual":      ("stag_cf_annual",          "quickfs_dj_cashflowstatementannual",  MIGRATE_CF_STATEMENT_DATA),
        "cf_quarter":     ("stag_cf_quarter",         "quickfs_dj_cashflowstatementquarter", MIGRATE_CF_STATEMENT_DATA),
    }

# ── S3 ─────────────────────────────────────────────────────────────────────────
def list_s3_keys(prefix: str) -> list[str]:
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix + "/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                keys.append(obj["Key"])
    return keys


def _exchange_code_from_key(key: str) -> str:
    # key format: {prefix}/{EXCHANGE}/{TICKER.EXCHANGE}.json
    parts = key.split("/")
    return parts[1] if len(parts) >= 3 else "UNKNOWN"


def _download_and_process(key: str) -> dict | None:
    """
    Runs in a thread: download one JSON from S3, parse it, return row dicts.
    Returns None on any failure so the main thread can count it as failed.
    """
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = json.loads(resp["Body"].read())
    except Exception as e:
        logging.warning(f"[{key}] S3 download failed: {e}")
        return None

    if not data or not data.get("General"):
        logging.warning(f"[{key}] skipped — missing or empty General section")
        return None

    # Skip SPACs and shells that have no financial history. These would be
    # inserted into TradedCompanies but have no balance sheet / income statement
    # rows, causing the valuation script to crash when it tries to compute EPV.
    financials = data.get("Financials", {})
    has_any_data = (
        financials.get("Income_Statement", {}).get("yearly")
        or financials.get("Income_Statement", {}).get("quarterly")
        or financials.get("Balance_Sheet", {}).get("yearly")
        or financials.get("Balance_Sheet", {}).get("quarterly")
    )
    if not has_any_data:
        logging.info(f"[{key}] skipped — no financial data (SPAC or shell)")
        return None

    try:
        return _process_company(data, _exchange_code_from_key(key))
    except Exception as e:
        logging.warning(f"[{key}] processing error: {e}")
        return None


# ── Shares matching helpers ────────────────────────────────────────────────────
def _nearest_shares(lkp: dict, date_str: str, max_days: int = 65) -> float | None:
    """
    Return the shares value from lkp whose key date is nearest to date_str.

    EODHD quarterly outstandingShares always uses calendar quarter-ends
    (Mar 31, Jun 30, Sep 30, Dec 31). A company with a non-standard fiscal
    quarter-end (e.g. Jan 31, Apr 30) has no exact match. This function finds
    the closest calendar quarter-end. The 65-day cap ensures we never
    accidentally cross into a neighbouring quarter's figure.
    """
    if not lkp:
        return None
    if date_str in lkp:
        return lkp[date_str]
    try:
        target = _date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
    closest = min(lkp, key=lambda d: abs((_date.fromisoformat(d) - target).days))
    if abs((_date.fromisoformat(closest) - target).days) <= max_days:
        return lkp[closest]
    return None


# ── Per-company row extraction ─────────────────────────────────────────────────
def _process_company(data: dict, exchange_code: str) -> dict:
    general    = data.get("General", {})
    financials = data.get("Financials", {})

    company_row = transform_traded_company(general, exchange_code)
    company_row["has_new_financials"] = True  # staging table excludes DB defaults
    qfs_symbol  = company_row["qfs_symbol"]

    rows = {
        "companies":      [company_row],
        "income_annual":  [],
        "income_quarter": [],
        "balance_annual": [],
        "balance_quarter":[],
        "cf_annual":      [],
        "cf_quarter":     [],
    }

    # ── Outstanding shares lookup ──────────────────────────────────────────────
    # EODHD stores outstandingShares as a top-level section separate from
    # Financials. It always uses calendar year-ends (Dec 31) for annual entries
    # and calendar quarter-ends (Mar/Jun/Sep/Dec 31) for quarterly entries,
    # regardless of the company's fiscal year.
    #
    # This means we cannot do an exact date match against income statement
    # period_end_dates for companies with non-December fiscal year-ends
    # (e.g. Agilent ends in October, some retailers end in January).
    #
    # Annual fix: match by calendar year only.
    #   "2025-10-31"[:4] == "2025" matches outstandingShares "2025-12-31"[:4]
    #
    # Quarterly fix: find the nearest calendar quarter-end within 65 days.
    #   Any fiscal quarter-end is at most ~62 days from the nearest calendar
    #   quarter-end (e.g. Jan 31 is 31 days from Dec 31), so 65 days is a
    #   safe window that never reaches the wrong quarter.
    outstanding = data.get("outstandingShares", {})

    # Annual lookup keyed by calendar year string e.g. "2025"
    shares_annual_lkp = {
        v["dateFormatted"][:4]: float(v["shares"])
        for v in outstanding.get("annual", {}).values()
        if v and v.get("dateFormatted") and v.get("shares") is not None
    }

    # Quarterly lookup keyed by full date string e.g. "2025-09-30"
    # (used by _nearest_shares below to find the closest calendar quarter-end)
    shares_quarter_lkp = {
        v["dateFormatted"]: float(v["shares"])
        for v in outstanding.get("quarterly", {}).values()
        if v and v.get("dateFormatted") and v.get("shares") is not None
    }

    # Diluted shares: commonStockSharesOutstanding from balance sheet is the
    # weighted-average diluted count used for EPS — more accurate for shares_diluted
    # than the basic end-of-period count in outstandingShares. Falls back to basic
    # when absent (zero-filled historical periods).
    _bs_shares = financials.get("Balance_Sheet", {})
    shares_diluted_annual_lkp: dict = {}
    for _p in _bs_shares.get("yearly", {}).values():
        if _p and _p.get("date") and _p.get("commonStockSharesOutstanding"):
            try:
                _v = float(_p["commonStockSharesOutstanding"])
                if _v > 0:
                    shares_diluted_annual_lkp[_p["date"][:4]] = _v
            except (TypeError, ValueError):
                pass

    shares_diluted_quarter_lkp: dict = {}
    for _p in _bs_shares.get("quarterly", {}).values():
        if _p and _p.get("date") and _p.get("commonStockSharesOutstanding"):
            try:
                _v = float(_p["commonStockSharesOutstanding"])
                if _v > 0:
                    shares_diluted_quarter_lkp[_p["date"]] = _v
            except (TypeError, ValueError):
                pass

    if MIGRATE_INCOME_STATEMENT_DATA:
        is_sec = financials.get("Income_Statement", {})
        for period in is_sec.get("yearly", {}).values():
            if period and period.get("date"):
                row = transform_income_statement(period, qfs_symbol)
                # Match annual shares by calendar year (first 4 chars of date)
                shares_eop = shares_annual_lkp.get(period["date"][:4])
                shares_dil = shares_diluted_annual_lkp.get(period["date"][:4]) or shares_eop
                # commonStockSharesOutstanding can be unreliable — diluted must never be < basic
                if shares_dil and shares_eop and shares_dil < shares_eop:
                    shares_dil = shares_eop
                row["shares_basic"]   = shares_eop
                row["shares_diluted"] = shares_dil
                row["shares_eop"]     = shares_eop
                rows["income_annual"].append(row)
        for period in is_sec.get("quarterly", {}).values():
            if period and period.get("date"):
                row = transform_income_statement(period, qfs_symbol)
                # Match quarterly shares to nearest calendar quarter-end
                shares_eop = _nearest_shares(shares_quarter_lkp, period["date"])
                shares_dil = _nearest_shares(shares_diluted_quarter_lkp, period["date"]) or shares_eop
                if shares_dil and shares_eop and shares_dil < shares_eop:
                    shares_dil = shares_eop
                row["shares_basic"]   = shares_eop
                row["shares_diluted"] = shares_dil
                row["shares_eop"]     = shares_eop
                rows["income_quarter"].append(row)

    if MIGRATE_BALANCE_SHEET_DATA:
        bs_sec = financials.get("Balance_Sheet", {})
        for period in bs_sec.get("yearly", {}).values():
            if period and period.get("date"):
                rows["balance_annual"].append(transform_balance_sheet(period, qfs_symbol))
        for period in bs_sec.get("quarterly", {}).values():
            if period and period.get("date"):
                rows["balance_quarter"].append(transform_balance_sheet(period, qfs_symbol))

    if MIGRATE_CF_STATEMENT_DATA:
        cf_sec = financials.get("Cash_Flow", {})
        for period in cf_sec.get("yearly", {}).values():
            if period and period.get("date"):
                rows["cf_annual"].append(transform_cash_flow(period, qfs_symbol))
        for period in cf_sec.get("quarterly", {}).values():
            if period and period.get("date"):
                rows["cf_quarter"].append(transform_cash_flow(period, qfs_symbol))

    return rows


# ── Batch flush ────────────────────────────────────────────────────────────────
def _update_shares_from_staging(conn, staging: str, target: str) -> None:
    """Update shares fields on existing income statement rows from staging data."""
    with conn.cursor() as cur:
        cur.execute(f"""
            UPDATE {target} t
            SET
                shares_basic   = s.shares_basic,
                shares_diluted = s.shares_diluted,
                shares_eop     = s.shares_eop
            FROM {staging} s
            WHERE t.qfs_symbol_id   = s.qfs_symbol_id
              AND t.period_end_date = s.period_end_date
              AND s.shares_diluted IS NOT NULL
        """)
    conn.commit()


def flush_batch(conn, batch: dict, registry: dict) -> None:
    for key, (staging, target, enabled) in registry.items():
        if not enabled or not batch[key]:
            continue
        df = pd.DataFrame(batch[key])
        bulk_insert_staging(conn, df, staging)
        insert_from_staging(
            conn,
            staging_table=staging,
            target_table=target,
            conflict_columns=CONFLICT_COLUMNS[key],
            cols_inserted_rows="qfs_symbol" if key == "companies" else "qfs_symbol_id",
        )
        if key in ("income_annual", "income_quarter"):
            _update_shares_from_staging(conn, staging, target)
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {staging}")
        conn.commit()

    for key in batch:
        batch[key] = []


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Migrate EODHD fundamentals from S3 to DB.")
    parser.add_argument(
        "--type",
        choices=["historical", "bulk"],
        default="historical",
        dest="data_type",
        help="historical = eodhd-fundamentals/ (default); bulk = eodhd-fundamentals-bulk/",
    )
    args = parser.parse_args()
    prefix = S3_PREFIX_BULK if args.data_type == "bulk" else S3_PREFIX_HISTORICAL

    logging.info("=== main.py start ===")
    logging.info(f"Data type: {args.data_type} (S3 prefix: {prefix})")
    logging.info(
        f"Flags — income={MIGRATE_INCOME_STATEMENT_DATA}, "
        f"balance={MIGRATE_BALANCE_SHEET_DATA}, "
        f"cf={MIGRATE_CF_STATEMENT_DATA}"
    )

    conn     = get_db_connection()
    registry = _build_registry()

    for key, (staging, target, enabled) in registry.items():
        if enabled:
            create_temp_staging_table(conn, target_table=target, staging_table=staging)

    keys = list_s3_keys(prefix)

    # for debugging: just process the first 10 keys
    # keys = keys[:1000]

    logging.info(f"Found {len(keys)} JSON files in S3")

    batch      = {k: [] for k in registry}
    processed  = 0
    failed     = 0

    # Submit keys in chunks so only CHUNK_SIZE futures exist in memory at once.
    # Submitting all futures upfront causes unbounded memory growth on large key sets.
    CHUNK_SIZE = S3_WORKERS * BATCH_SIZE

    with ThreadPoolExecutor(max_workers=S3_WORKERS) as pool:
        for chunk_start in range(0, len(keys), CHUNK_SIZE):
            chunk = keys[chunk_start:chunk_start + CHUNK_SIZE]
            futures = [pool.submit(_download_and_process, key) for key in chunk]

            for future in as_completed(futures):
                rows = future.result()
                if rows is None:
                    failed += 1
                    continue

                for k in batch:
                    batch[k].extend(rows[k])
                processed += 1

                if processed % BATCH_SIZE == 0:
                    flush_batch(conn, batch, registry)
                    logging.info(f"Flushed batch — processed={processed}, failed={failed}")

    # Final flush for remaining rows
    if any(batch[k] for k in batch):
        flush_batch(conn, batch, registry)

    conn.close()
    logging.info(f"=== main.py complete — processed={processed}, failed={failed} ===")


if __name__ == "__main__":
    main()
