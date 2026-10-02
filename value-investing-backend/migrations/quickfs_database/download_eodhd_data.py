import json
import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

from migration_utils import get_exchanges

load_dotenv()

API_TOKEN = os.environ["EODHD_API_TOKEN"]
S3_BUCKET = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = "eodhd-fundamentals"

MAX_WORKERS = 5
RATE_LIMIT_PER_MINUTE = 950  # slightly under 1000 to stay safe
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds; multiplied by attempt number

# Set to True to reprocess only symbols that failed in the previous run
RETRY_FAILED_ONLY = False
FAILED_SYMBOLS_FILE = Path(__file__).parent / "failed_symbols.json"
# Tracks successfully downloaded symbols across runs — delete to start fresh
PROGRESS_FILE = Path(__file__).parent / "download_progress.txt"

BASE_URL = "https://eodhd.com/api"

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    filename=log_dir / "download_eodhd_data.log",
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


class RateLimiter:
    """Global token-bucket rate limiter. Serializes request issuance across threads."""

    def __init__(self, max_per_minute: int):
        self._lock = threading.Lock()
        self._interval = 60.0 / max_per_minute
        self._next_allowed = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
            self._next_allowed = time.monotonic() + self._interval


_rate_limiter = RateLimiter(max_per_minute=RATE_LIMIT_PER_MINUTE)


def _s3_key(exchange_code: str, ticker_exchange: str) -> str:
    return f"{S3_PREFIX}/{exchange_code}/{ticker_exchange}.json"


def _load_progress() -> set[str]:
    """
    Return set of symbols already successfully downloaded.
    Delete download_progress.txt to force a full re-fetch from scratch.
    """
    if not PROGRESS_FILE.exists():
        return set()
    return set(PROGRESS_FILE.read_text().splitlines())


def get_exchange_symbols(exchange_code: str) -> list[str]:
    """Return ['AAPL.US', ...] for all common stocks on one exchange."""
    resp = requests.get(
        f"{BASE_URL}/exchange-symbol-list/{exchange_code}",
        params={"api_token": API_TOKEN, "fmt": "json", "type": "common_stock"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        logging.warning(f"[{exchange_code}] unexpected symbol-list type: {type(data)}")
        return []

    return [f"{s['Code']}.{exchange_code}" for s in data if s.get("Code")]


def _fetch_and_upload(ticker_exchange: str, exchange_code: str) -> str:
    """
    Fetch fundamentals JSON from EODHD and store in S3.
    - Retries up to MAX_RETRIES times on transient network errors.
    - On HTTP 429 (daily limit), sleeps for Retry-After seconds without consuming a retry.
    Returns 'ok' or 'failed'.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        _rate_limiter.acquire()
        try:
            resp = requests.get(
                f"{BASE_URL}/fundamentals/{ticker_exchange}",
                params={"api_token": API_TOKEN, "fmt": "json"},
                timeout=30,
            )

            # Daily API credit limit exhausted — wait for reset, then retry
            while resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logging.warning(
                    f"[{ticker_exchange}] daily limit hit — sleeping {retry_after}s (Retry-After header)"
                )
                time.sleep(retry_after)
                _rate_limiter.acquire()
                resp = requests.get(
                    f"{BASE_URL}/fundamentals/{ticker_exchange}",
                    params={"api_token": API_TOKEN, "fmt": "json"},
                    timeout=30,
                )

            if resp.status_code != 200:
                logging.warning(f"[{ticker_exchange}] HTTP {resp.status_code}: {resp.text[:200]}")
                return "failed"

            s3.put_object(
                Bucket=S3_BUCKET,
                Key=_s3_key(exchange_code, ticker_exchange),
                Body=resp.content,
                ContentType="application/json",
            )
            return "ok"

        except Exception as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * attempt
                logging.warning(f"[{ticker_exchange}] attempt {attempt} failed: {e} — retrying in {wait}s")
                time.sleep(wait)
            else:
                logging.warning(f"[{ticker_exchange}] all {MAX_RETRIES} attempts failed: {e}")
                return "failed"

    return "failed"


def _process_symbols(symbols_by_exchange: dict[str, list[str]]) -> list[dict]:
    """
    Run _fetch_and_upload for every symbol.
    Appends each success to PROGRESS_FILE (one symbol per line) so runs can be resumed.
    Returns list of failed entries: [{"ticker_exchange": "AFFL.US", "exchange_code": "US"}, ...]
    """
    failed: list[dict] = []

    with open(PROGRESS_FILE, "a") as progress_f:
        for code, symbols in symbols_by_exchange.items():
            logging.info(f"[{code}] {len(symbols)} stocks to process")
            if not symbols:
                continue

            ok = 0
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {
                    pool.submit(_fetch_and_upload, sym, code): sym
                    for sym in symbols
                }
                for i, future in enumerate(as_completed(futures), 1):
                    sym = futures[future]
                    if future.result() == "ok":
                        ok += 1
                        progress_f.write(sym + "\n")
                        progress_f.flush()
                    else:
                        failed.append({"ticker_exchange": sym, "exchange_code": code})

                    if i % 500 == 0:
                        exchange_failed = sum(1 for f in failed if f["exchange_code"] == code)
                        logging.info(
                            f"[{code}] progress {i}/{len(symbols)} (ok={ok}, failed={exchange_failed})"
                        )

            exchange_failed = sum(1 for f in failed if f["exchange_code"] == code)
            logging.info(f"[{code}] done — ok={ok}, failed={exchange_failed}")

    return failed


if __name__ == "__main__":
    logging.info("=== download_eodhd_data.py start ===")

    if RETRY_FAILED_ONLY:
        if not FAILED_SYMBOLS_FILE.exists():
            logging.error(f"RETRY_FAILED_ONLY=True but {FAILED_SYMBOLS_FILE} not found — nothing to retry")
            raise SystemExit(1)

        entries: list[dict] = json.loads(FAILED_SYMBOLS_FILE.read_text())
        logging.info(f"Retrying {len(entries)} previously failed symbols")

        symbols_by_exchange: dict[str, list[str]] = {}
        for entry in entries:
            symbols_by_exchange.setdefault(entry["exchange_code"], []).append(entry["ticker_exchange"])
    else:
        already_done = _load_progress()
        if already_done:
            logging.info(f"Resuming — {len(already_done)} symbols already downloaded, skipping these")

        exchanges = get_exchanges(API_TOKEN)
        logging.info(f"Found {len(exchanges)} exchanges from EODHD")

        symbols_by_exchange = {}
        for exchange in exchanges:
            code = exchange["Code"]
            name = exchange.get("Name", code)
            logging.info(f"[{code}] {name} — fetching symbol list...")
            try:
                all_symbols = get_exchange_symbols(code)
                remaining = [s for s in all_symbols if s not in already_done]
                skipped = len(all_symbols) - len(remaining)
                if skipped:
                    logging.info(f"[{code}] skipping {skipped} already downloaded, {len(remaining)} remaining")
                symbols_by_exchange[code] = remaining
            except Exception as e:
                logging.error(f"[{code}] failed to get symbol list: {e}")
                symbols_by_exchange[code] = []

    failed = _process_symbols(symbols_by_exchange)

    # Always overwrite — never append — so the file reflects only the current run's failures
    if failed:
        FAILED_SYMBOLS_FILE.write_text(json.dumps(failed, indent=2))
        logging.info(f"Wrote {len(failed)} failed symbols to {FAILED_SYMBOLS_FILE}")
    elif FAILED_SYMBOLS_FILE.exists():
        FAILED_SYMBOLS_FILE.unlink()
        logging.info("All symbols succeeded — removed stale failed_symbols.json")

    logging.info(f"=== download_eodhd_data.py complete — {len(failed)} failures ===")
