import os
import time
import psycopg2
import requests
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.environ["EODHD_API_TOKEN"]
MAX_RETRIES = 3
RETRY_BACKOFF = 10  # seconds; multiplied by attempt number (10s, 20s, 30s)


def get_active_currency_pairs(conn) -> list[tuple[str, str]]:
    """
    (reporting_currency, trading_currency) pairs that actually need conversion,
    derived from whatever fundamentals + TradedCompanies rows currently exist.
    Same-currency companies (the vast majority) never produce a pair here, since
    reporting_currency == trading currency means no conversion is needed.
    """
    query = """
        SELECT DISTINCT reporting_currency, trading_currency FROM (
            SELECT i.reporting_currency, tc.currency AS trading_currency
            FROM quickfs_dj_incomestatementannual i
            JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = i.qfs_symbol_id
            UNION
            SELECT i.reporting_currency, tc.currency AS trading_currency
            FROM quickfs_dj_incomestatementquarter i
            JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = i.qfs_symbol_id
            UNION
            SELECT b.reporting_currency, tc.currency AS trading_currency
            FROM quickfs_dj_balancesheetquarter b
            JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = b.qfs_symbol_id
        ) pairs
        WHERE reporting_currency IS NOT NULL
          AND trading_currency IS NOT NULL
          AND reporting_currency != trading_currency
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


# Data-vendor "minor unit" pseudo-currencies: not real ISO-4217 codes, no actual FX
# market exists for them, so EODHD's forex endpoint returns "NA". GBX ("pence
# sterling") is the common one - many LSE-listed stocks quote in pence rather than
# pounds, where 100 GBX = 1 GBP. Resolve to the real currency and scale instead.
MINOR_UNIT_CURRENCIES = {
    "GBX": ("GBP", 100),  # (real ISO currency, units of the minor currency per 1 unit of the real one)
}


def _resolve_real_currency(ccy: str) -> tuple[str, float]:
    return MINOR_UNIT_CURRENCIES.get(ccy, (ccy, 1))


def fetch_rate(from_ccy: str, to_ccy: str) -> float | None:
    """Latest available rate: units of to_ccy per 1 unit of from_ccy."""
    real_from, from_scale = _resolve_real_currency(from_ccy)
    real_to, to_scale = _resolve_real_currency(to_ccy)

    if real_from == real_to:
        # e.g. GBP -> GBX: no real FX conversion needed, just a unit-scale factor
        return to_scale / from_scale

    raw_rate = _fetch_raw_rate(real_from, real_to)
    if raw_rate is None:
        return None

    # raw_rate is units of real_to per 1 unit of real_from. Rescale both ends to
    # get units of to_ccy per 1 unit of from_ccy.
    return raw_rate * to_scale / from_scale


def _fetch_raw_rate(from_ccy: str, to_ccy: str) -> float | None:
    """Latest available rate for a real ISO currency pair: units of to_ccy per 1 unit of from_ccy."""
    url = f"https://eodhd.com/api/real-time/{from_ccy}{to_ccy}.FOREX"
    params = {"api_token": API_TOKEN, "fmt": "json"}

    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code == 429:
            wait = RETRY_BACKOFF * attempt
            print(f"[FX] {from_ccy}{to_ccy} 429 rate limit — sleeping {wait}s")
            time.sleep(wait)
            continue

        if resp.status_code >= 500:
            wait = RETRY_BACKOFF * attempt
            print(f"[FX] {from_ccy}{to_ccy} HTTP {resp.status_code} — retrying in {wait}s")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"[FX] {from_ccy}{to_ccy} HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        close = data.get("close")
        if close is None:
            print(f"[FX] {from_ccy}{to_ccy} response missing 'close': {data}")
            return None

        try:
            return float(close)
        except (TypeError, ValueError):
            print(f"[FX] {from_ccy}{to_ccy} non-numeric close: {close!r}")
            return None

    print(f"[FX] {from_ccy}{to_ccy} failed after {MAX_RETRIES} attempts")
    return None


def upsert_rates(conn, rates: list[tuple[str, str, float]]) -> None:
    """rates: [(from_currency, to_currency, rate), ...]"""
    if not rates:
        return
    query = """
        INSERT INTO quickfs_dj_fxrate (from_currency, to_currency, rate, updated_at)
        VALUES %s
        ON CONFLICT (from_currency, to_currency)
        DO UPDATE SET rate = EXCLUDED.rate, updated_at = EXCLUDED.updated_at
    """
    with conn.cursor() as cur:
        execute_values(
            cur, query, rates,
            template="(%s, %s, %s, NOW())",
        )
    conn.commit()


def main():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        database=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        port=os.environ["DB_PORT"],
    )

    try:
        pairs = get_active_currency_pairs(conn)
        print(f"[FX] {len(pairs)} currency pair(s) need conversion: {pairs}")

        rates = []
        for from_ccy, to_ccy in pairs:
            rate = fetch_rate(from_ccy, to_ccy)
            if rate is not None:
                print(f"[FX] {from_ccy} -> {to_ccy}: {rate}")
                rates.append((from_ccy, to_ccy, rate))

        upsert_rates(conn, rates)
        print(f"[FX] Upserted {len(rates)}/{len(pairs)} rate(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    print("#######################################")
    print("Start migrating FX rates")
    print("#######################################\n\n\n")

    main()

    print("#######################################")
    print("End migrating FX rates")
    print("#######################################\n\n\n")
