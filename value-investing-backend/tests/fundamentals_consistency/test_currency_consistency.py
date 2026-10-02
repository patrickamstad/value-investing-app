import pytest
from django.db.models import F
from quickfs_dj.models import IncomeStatementAnnual, FxRate, ScreenerData

pytestmark = pytest.mark.django_db(databases=["default"])

# These guard against the currency-mismatch bug where a company's fundamentals are
# filed in one currency (e.g. CNY) but it trades in another (e.g. USD) - see
# migrate_valuation_data.py / migrate_screener_data.py for where the FX conversion
# actually happens. Once a company's data has been re-ingested through the FX-aware
# pipeline (migrate_fx_rates.py -> migrate_valuation_data.py -> migrate_screener_data.py)
# these should always pass. Immediately after this field/model is introduced, existing
# rows won't have reporting_currency/FxRate populated yet - that's expected transitional
# behavior until the next full pipeline run backfills it, not a bug in already-filed data.
#
# Note: these checks aren't numeric-identity comparisons (unlike test_income_statement.py
# / test_balance_sheet.py), so they don't use helpers.report() - its failure formatting
# assumes numeric expected/actual values, which doesn't fit "missing currency" style checks.


def _print_report(label: str, total: int, passed: int, failures: list[str]) -> None:
    pct = 100 * passed / total if total else 0.0
    print(f"\n{'─' * 60}")
    print(f"{label}: {passed}/{total} passed ({pct:.1f}%)")
    if failures:
        print("  Sample failures:")
        for line in failures[:5]:
            print(f"    {line}")


def test_reporting_currency_completeness():
    """
    Every IncomeStatementAnnual row should carry the reporting_currency captured at
    ingestion (eodhd_field_mappings.py). A gap here means a currency-mismatched company
    could silently fall back to fx_rate=1.0 in migrate_valuation_data.py /
    migrate_screener_data.py instead of actually being converted.
    """
    total = IncomeStatementAnnual.objects.count()
    missing_qs = IncomeStatementAnnual.objects.filter(reporting_currency__isnull=True)
    missing = missing_qs.count()

    sample = [
        f"{r.qfs_symbol_id} {r.period_end_date}: reporting_currency is NULL"
        for r in missing_qs.order_by("qfs_symbol_id", "period_end_date")[:5]
    ]
    _print_report("reporting_currency_completeness", total, total - missing, sample)
    assert missing == 0, f"{missing}/{total} IncomeStatementAnnual rows missing reporting_currency"


def test_fx_rate_coverage():
    """
    Every (reporting_currency, trading_currency) pair actually in use - where a
    company's filing currency differs from its trading currency - must have a
    corresponding FxRate row. A missing row silently falls back to a 1.0 rate in
    migrate_valuation_data.py / migrate_screener_data.py, which is exactly the
    original bug this fix addresses.
    """
    pairs_in_use = set(
        IncomeStatementAnnual.objects
        .exclude(reporting_currency__isnull=True)
        .exclude(qfs_symbol__currency__isnull=True)
        .exclude(reporting_currency=F("qfs_symbol__currency"))
        .values_list("reporting_currency", "qfs_symbol__currency")
        .distinct()
    )
    covered_pairs = set(FxRate.objects.values_list("from_currency", "to_currency"))
    missing_pairs = pairs_in_use - covered_pairs

    sample = [f"missing FxRate for {from_ccy} -> {to_ccy}" for from_ccy, to_ccy in list(missing_pairs)[:5]]
    _print_report("fx_rate_coverage", len(pairs_in_use), len(pairs_in_use) - len(missing_pairs), sample)
    assert not missing_pairs, f"Missing FxRate rows for pairs: {missing_pairs}"


def test_valuation_within_sane_multiple_of_price():
    """
    epv_per_share / penman_per_share should stay within a broad plausible multiple of
    the trading price for every company. A missed currency conversion blows this ratio
    out by roughly the FX rate magnitude (e.g. ~7x for CNY/USD, ~150x for JPY/USD) -
    this is the tripwire that catches that regression regardless of which code path
    reintroduces it, without needing to know which fields were supposed to be converted.
    """
    LOWER, UPPER = 0.02, 50.0
    failures = []
    checked = 0

    for field in ("epv_per_share", "penman_per_share"):
        rows = ScreenerData.objects.exclude(price__isnull=True).exclude(**{f"{field}__isnull": True})
        for row in rows.iterator(chunk_size=2000):
            price = row.price
            value = getattr(row, field)
            if price is None or value is None or price <= 0 or value <= 0:
                continue
            checked += 1
            ratio = value / price
            if not (LOWER <= ratio <= UPPER):
                failures.append(f"{row.qfs_symbol_id} {field}: ratio {ratio:.4f} outside [{LOWER}, {UPPER}]")

    _print_report("valuation_within_sane_multiple_of_price", checked, checked - len(failures), failures)
    assert not failures, (
        f"{len(failures)} valuation/price ratios out of sane range "
        f"(likely a missed currency conversion): {failures[:5]}"
    )
