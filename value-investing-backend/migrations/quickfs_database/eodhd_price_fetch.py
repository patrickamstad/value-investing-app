import csv
import psycopg2
import requests
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()


def _batch_update_close_prices(cur, updates: list[tuple[str, float]], chunk_size: int = 3000) -> None:
    """updates: [(qfs_symbol, close_price), ...]"""
    update_query = """
        UPDATE quickfs_dj_tradedcompanies AS q
        SET last_close_price = v.price
        FROM (VALUES %s) AS v(qfs_symbol, price)
        WHERE q.qfs_symbol = v.qfs_symbol;
    """
    for i in range(0, len(updates), chunk_size):
        execute_values(cur, update_query, updates[i:i + chunk_size])


def _fetch_all_qfs_symbols(conn) -> list[str]:
    """Return all qfs_symbol values currently in the DB."""
    with conn.cursor() as cur:
        cur.execute("SELECT qfs_symbol FROM quickfs_dj_tradedcompanies WHERE qfs_symbol IS NOT NULL")
        return [row[0] for row in cur.fetchall()]


def _group_symbols_by_exchange(symbols: list[str]) -> dict[str, set[str]]:
    """
    Derive exchange code from qfs_symbol suffix and group.
    "AAPL.US" → exchange "US"
    Returns: {"US": {"AAPL.US", "MSFT.US"}, "LSE": {"BGO.LSE", ...}, ...}
    """
    exchange_map: dict[str, set[str]] = {}
    for sym in symbols:
        if "." not in sym:
            continue
        exchange = sym.rsplit(".", 1)[-1]
        exchange_map.setdefault(exchange, set()).add(sym)
    return exchange_map


def _fetch_bulk_eod_prices(
    exchange_code: str,
    needed_symbols: set[str],
    api_token: str,
    timeout: int = 60,
) -> dict[str, float]:
    """
    Call EODHD bulk EOD endpoint once for one exchange.
    Returns {qfs_symbol: close_price} for symbols present in needed_symbols.
    """
    url = f"https://eodhd.com/api/eod-bulk-last-day/{exchange_code}?api_token={api_token}"
    print(f"[EODHD] GET {url}")

    found: dict[str, float] = {}

    with requests.get(url, stream=True, timeout=timeout) as resp:
        if resp.status_code != 200:
            print(f"[EODHD] [{exchange_code}] HTTP {resp.status_code}: {resp.text[:200]}")
            return found

        # Response columns: Code, Ex, Date, Open, High, Low, Close, Adjusted_close, Volume
        lines = (line.decode("utf-8", errors="replace") for line in resp.iter_lines() if line)
        reader = csv.DictReader(lines)

        for row in reader:
            code      = (row.get("Code") or "").strip()
            ex        = (row.get("Ex") or "").strip()
            close_str = (row.get("Close") or "").strip()

            if not code or not ex or not close_str:
                continue

            sym = f"{code}.{ex}"
            if sym not in needed_symbols:
                continue

            try:
                found[sym] = float(close_str)
            except ValueError:
                continue

    print(f"[EODHD] [{exchange_code}] matched {len(found)}/{len(needed_symbols)} symbols")
    return found


def update_close_prices_via_eodhd_bulk(
    dbname: str,
    user: str,
    password: str,
    host: str,
    port: int,
    eodhd_api_token: str,
    db_update_chunk_size: int = 3000,
) -> None:
    conn = None
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        print(f"Connected: {conn.get_dsn_parameters()['dbname']}")

        # 1. Load all symbols from DB
        all_symbols = _fetch_all_qfs_symbols(conn)
        print(f"Total symbols in DB: {len(all_symbols)}")

        # 2. Group by exchange — determines exactly how many API calls we make
        exchange_map = _group_symbols_by_exchange(all_symbols)
        print(f"Unique exchanges to fetch: {sorted(exchange_map.keys())}")

        # 3. One bulk API call per exchange
        all_prices: dict[str, float] = {}
        for exchange_code, needed in exchange_map.items():
            prices = _fetch_bulk_eod_prices(exchange_code, needed, eodhd_api_token)
            all_prices.update(prices)

        # 4. Batch update DB
        updates = list(all_prices.items())
        print(f"Updating {len(updates)} close prices in DB")

        with conn:
            with conn.cursor() as cur:
                _batch_update_close_prices(cur, updates, chunk_size=db_update_chunk_size)

        print("Close price update committed successfully.")

    finally:
        if conn:
            conn.close()
