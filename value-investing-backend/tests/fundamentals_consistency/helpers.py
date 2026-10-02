import csv
from datetime import datetime
from pathlib import Path

TOLERANCE = 0.001  # 0.1% relative tolerance
FAILURES_DIR = Path(__file__).parent / "failure_reports"

_run_dir: Path | None = None


def _get_run_dir() -> Path:
    global _run_dir
    if _run_dir is None:
        _run_dir = FAILURES_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        _run_dir.mkdir(parents=True, exist_ok=True)
    return _run_dir


def rel_diff(expected: float, actual: float) -> float:
    """Symmetric relative difference: |expected - actual| / max(|expected|, |actual|).
    Returns 0.0 when both values are zero."""
    denom = max(abs(expected), abs(actual))
    return 0.0 if denom == 0 else abs(expected - actual) / denom


def check_identity(queryset, compute_expected, get_actual, get_key):
    """
    Iterate queryset and check whether compute_expected(row) ≈ get_actual(row).

    None handling:
      expected=None, actual=None  → skip (no data)
      expected=None, actual=value → failure (derived exists but components missing)
      expected=value, actual=None → failure (components exist but derived missing)
      both present                → compare within TOLERANCE

    Returns (total_checked, passed, failures).
    """
    total = passed = 0
    failures = []

    for row in queryset.iterator(chunk_size=2000):
        try:
            expected = compute_expected(row)
        except (TypeError, AttributeError):
            expected = None

        actual = get_actual(row)

        if expected is None and actual is None:
            continue  # no data at all — nothing to verify

        total += 1
        symbol, date = get_key(row)

        if expected is None:
            failures.append({
                "symbol": symbol,
                "date": str(date),
                "expected": None,
                "actual": round(actual),
                "diff_pct": "inputs NULL",
            })
        elif actual is None:
            failures.append({
                "symbol": symbol,
                "date": str(date),
                "expected": round(expected),
                "actual": None,
                "diff_pct": "actual NULL",
            })
        elif rel_diff(expected, actual) <= TOLERANCE:
            passed += 1
        else:
            failures.append({
                "symbol": symbol,
                "date": str(date),
                "expected": round(expected),
                "actual": round(actual),
                "diff_pct": round(rel_diff(expected, actual) * 100, 3),
            })

    return total, passed, failures


def report(label: str, total: int, passed: int, failures: list) -> None:
    pct = 100 * passed / total if total else 0.0
    print(f"\n{'─' * 60}")
    print(f"{label}: {passed}/{total} passed ({pct:.1f}%)")

    if failures:
        print("  Sample failures:")
        for f in failures[:5]:
            exp = f"{f['expected']:,.0f}" if f["expected"] is not None else "NULL"
            act = f"{f['actual']:,.0f}" if f["actual"] is not None else "NULL"
            print(f"    {f['symbol']} {f['date']}: expected {exp}  got {act}  ({f['diff_pct']})")

        path = _get_run_dir() / f"{label}.csv"
        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["symbol", "date", "expected", "actual", "diff_pct"])
            writer.writeheader()
            writer.writerows(failures)
        print(f"  Full list → {path}")
