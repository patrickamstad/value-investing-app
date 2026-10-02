import json
import os
import time
import logging
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

from migration_utils import get_exchanges

load_dotenv()

API_TOKEN = os.environ["EODHD_API_TOKEN"]
S3_BUCKET = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = "eodhd-fundamentals-bulk"

BULK_PAGE_SIZE = 500  # max companies per request; each request costs 100 API credits
BASE_URL = "https://eodhd.com/api"
MAX_RETRIES = 3
RETRY_BACKOFF = 10  # seconds; multiplied by attempt number (10s, 20s, 30s)

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    filename=log_dir / "download_eodhd_bulk.log",
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
)


def _s3_key(exchange_code: str, ticker_exchange: str) -> str:
    return f"{S3_PREFIX}/{exchange_code}/{ticker_exchange}.json"


def normalize_company(company: dict) -> dict:
    """
    Rewrite a bulk v1.2 company dict into the format main.py expects.

    Transformation 1 — period keys:
      Bulk uses numbered keys ("yearly_last_0", "quarterly_last_1", …).
      main.py expects date-keyed dicts ("yearly": {"2024-09-30": {...}, …}).
      Each period's own "date" field becomes the dict key; periods with
      date == "0000-00-00" are dropped. Non-period keys (e.g. "currency_symbol")
      pass through unchanged.

    Transformation 2 — outstandingShares:
      Bulk has no per-period share history, only SharesStats.SharesOutstanding
      (the current total). A synthetic "outstandingShares" section is injected
      with that single value repeated for every income-statement period, so
      main.py can populate shares_basic and shares_eop rather than leaving them
      NULL. shares_diluted is unaffected — it reads commonStockSharesOutstanding
      from the Balance_Sheet periods directly (already per-period in bulk).

    Example input (bulk):
        "yearly_last_0": {"date": "2024-09-30", "totalRevenue": 391035000000}
        "yearly_last_1": {"date": "2023-09-30", "totalRevenue": 383285000000}
        SharesStats.SharesOutstanding = 15115823000

    Example output (normalized):
        "yearly": {"2024-09-30": {"date": "2024-09-30", "totalRevenue": 391035000000},
                   "2023-09-30": {"date": "2023-09-30", "totalRevenue": 383285000000}}
        outstandingShares.annual:
            {"0": {"dateFormatted": "2024-09-30", "shares": 15115823000},
             "1": {"dateFormatted": "2023-09-30", "shares": 15115823000}}
    """
    financials = company.get("Financials", {})
    for section in ("Income_Statement", "Balance_Sheet", "Cash_Flow"):
        sec = financials.get(section, {})
        yearly: dict = {}
        quarterly: dict = {}
        preserved: dict = {}
        for k, v in sec.items():
            if k.startswith("yearly_last_"):
                if isinstance(v, dict) and v.get("date") and v["date"] != "0000-00-00":
                    # Bulk periods already carry their own currency_symbol (verified
                    # against a real bulk response), but fall back to the section-level
                    # currency_symbol just in case a period is ever missing it.
                    v.setdefault("currency_symbol", sec.get("currency_symbol"))
                    yearly[v["date"]] = v
            elif k.startswith("quarterly_last_"):
                if isinstance(v, dict) and v.get("date") and v["date"] != "0000-00-00":
                    v.setdefault("currency_symbol", sec.get("currency_symbol"))
                    quarterly[v["date"]] = v
            else:
                preserved[k] = v
        financials[section] = {**preserved, "yearly": yearly, "quarterly": quarterly}

    shares_outstanding = company.get("SharesStats", {}).get("SharesOutstanding")
    if shares_outstanding:
        annual_dates = list(financials.get("Income_Statement", {}).get("yearly", {}).keys())
        quarterly_dates = list(financials.get("Income_Statement", {}).get("quarterly", {}).keys())
        company["outstandingShares"] = {
            "annual": {
                str(i): {"dateFormatted": d, "shares": shares_outstanding}
                for i, d in enumerate(annual_dates)
            },
            "quarterly": {
                str(i): {"dateFormatted": d, "shares": shares_outstanding}
                for i, d in enumerate(quarterly_dates)
            },
        }
    else:
        company["outstandingShares"] = {}

    return company


def _fetch_bulk_page(exchange_code: str, offset: int) -> list[dict]:
    """Fetch one page of bulk fundamentals (costs 100 API credits per call)."""
    params = {
        "api_token": API_TOKEN,
        "offset": offset,
        "limit": BULK_PAGE_SIZE,
        "version": "1.2",
        "fmt": "json",
    }
    url = f"{BASE_URL}/bulk-fundamentals/{exchange_code}"

    for attempt in range(1, MAX_RETRIES + 1):
        # Large exchanges (US, NASDAQ) can take several minutes — generous timeout.
        resp = requests.get(url, params=params, timeout=600)

        while resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            logging.warning(f"[{exchange_code}] 429 rate limit — sleeping {retry_after}s")
            time.sleep(retry_after)
            resp = requests.get(url, params=params, timeout=600)

        if resp.status_code >= 500:
            wait = RETRY_BACKOFF * attempt
            logging.warning(
                f"[{exchange_code}] offset={offset}: HTTP {resp.status_code} "
                f"(attempt {attempt}/{MAX_RETRIES}) — retrying in {wait}s"
            )
            time.sleep(wait)
            continue

        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.values())
        return []

    raise requests.HTTPError(f"[{exchange_code}] offset={offset}: failed after {MAX_RETRIES} retries")


def process_exchange(exchange_code: str) -> tuple[int, int]:
    """
    Fetch all companies for one exchange via paginated bulk endpoint,
    normalize, and save each to S3. Returns (companies_saved, api_calls_used).
    """
    offset = 0
    total_saved = 0
    api_calls = 0

    while True:
        try:
            companies = _fetch_bulk_page(exchange_code, offset)
        except Exception as e:
            logging.error(f"[{exchange_code}] bulk fetch failed at offset={offset}: {e}")
            break

        api_calls += 1
        if not companies:
            break

        saved = 0
        for company in companies:
            code = company.get("General", {}).get("Code")
            if not code:
                continue
            ticker_exchange = f"{code}.{exchange_code}"
            try:
                normalized = normalize_company(company)
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=_s3_key(exchange_code, ticker_exchange),
                    Body=json.dumps(normalized),
                    ContentType="application/json",
                )
                saved += 1
            except Exception as e:
                logging.warning(f"[{ticker_exchange}] failed to normalize/upload: {e}")

        total_saved += saved
        logging.info(
            f"[{exchange_code}] offset={offset}: {len(companies)} fetched, {saved} saved "
            f"(~{api_calls * 100} credits used so far)"
        )

        if len(companies) < BULK_PAGE_SIZE:
            break
        offset += BULK_PAGE_SIZE

    return total_saved, api_calls


if __name__ == "__main__":
    logging.info("=== download_eodhd_bulk.py start ===")

    exchanges = get_exchanges(API_TOKEN)
    logging.info(f"Found {len(exchanges)} exchanges from EODHD")

    total_companies = 0
    total_api_calls = 0

    for exchange in exchanges:
        code = exchange.get("Code", "")
        if not code:
            continue
        name = exchange.get("Name", code)
        logging.info(f"[{code}] {name} — starting bulk download...")
        try:
            count, calls = process_exchange(code)
            total_companies += count
            total_api_calls += calls
            logging.info(f"[{code}] done — {count} companies, {calls} API calls (~{calls * 100} credits)")
        except Exception as e:
            logging.error(f"[{code}] exchange failed: {e}")

    logging.info(
        f"=== download_eodhd_bulk.py complete — "
        f"{total_companies} companies, {total_api_calls} API calls "
        f"(~{total_api_calls * 100} credits used) ==="
    )
