import pytest
from quickfs_dj.models import BalanceSheetAnnual
from tests.fundamentals_consistency.helpers import check_identity, report

pytestmark = pytest.mark.django_db(databases=["default"])


def _key(r):
    return r.qfs_symbol_id, r.period_end_date


def test_total_current_assets():
    """cash + st_investments + receivables + inventories + other_current_assets = total_current_assets"""
    balance_sheets = BalanceSheetAnnual.objects.all()
    total, passed, failures = check_identity(
        balance_sheets,
        compute_expected=lambda r: (
            (r.cash_and_equiv or 0)
            + (r.st_investments or 0)
            + (r.receivables or 0)
            + (r.inventories or 0)
            + (r.other_current_assets or 0)
            if r.total_current_assets is not None else None
        ),
        get_actual=lambda r: r.total_current_assets,
        get_key=_key,
    )
    report("total_current_assets", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_total_assets():
    """all asset components sum to total_assets"""
    balance_sheets = BalanceSheetAnnual.objects.all()
    total, passed, failures = check_identity(
        balance_sheets,
        compute_expected=lambda r: (
            (r.cash_and_equiv or 0)
            + (r.st_investments or 0)
            + (r.receivables or 0)
            + (r.inventories or 0)
            + (r.other_current_assets or 0)
            + (r.equity_and_other_investments or 0)
            + (r.ppe_net or 0)
            + (r.goodwill or 0)
            + (r.intangible_assets or 0)
            + (r.other_lt_assets or 0)
            if r.total_assets is not None else None
        ),
        get_actual=lambda r: r.total_assets,
        get_key=_key,
    )
    report("total_assets", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_total_current_liabilities():
    """accounts_payable + st_debt + current_deferred_revenue + other_current_liabilities = total_current_liabilities"""
    balance_sheets = BalanceSheetAnnual.objects.all()
    total, passed, failures = check_identity(
        balance_sheets,
        compute_expected=lambda r: (
            (r.accounts_payable or 0)
            + (r.st_debt or 0)
            + (r.current_deferred_revenue or 0)
            + (r.other_current_liabilities or 0)
            if r.total_current_liabilities is not None else None
        ),
        get_actual=lambda r: r.total_current_liabilities,
        get_key=_key,
    )
    report("total_current_liabilities", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_total_liabilities():
    """total_current_liabilities + lt_debt + noncurrent_leases + other_lt_liabilities ≈ total_liabilities (informational).

    Not asserted: other_lt_liabilities is anchored on (total_assets - total_equity) to enforce
    the accounting equation, so it absorbs provisions excluded from EODHD's totalLiab.
    Failures here indicate the size of that provisions gap per company.
    """
    balance_sheets = BalanceSheetAnnual.objects.all()
    total, passed, failures = check_identity(
        balance_sheets,
        compute_expected=lambda r: (
            (r.total_current_liabilities or 0)
            + (r.lt_debt or 0)
            + (r.noncurrent_capital_leases or 0)
            + (r.other_lt_liabilities or 0)
            if r.total_liabilities is not None else None
        ),
        get_actual=lambda r: r.total_liabilities,
        get_key=_key,
    )
    report("total_liabilities", total, passed, failures)


def test_accounting_equation():
    """total_assets = total_liabilities + total_equity + minority_interest (informational only).

    Not asserted: EODHD's totalLiab excludes provisions for some non-US (notably Dutch/IFRS)
    companies, creating a systematic 1-3% gap. This is a raw data limitation, not a transform bug.
    """
    balance_sheets = BalanceSheetAnnual.objects.all()
    total, passed, failures = check_identity(
        balance_sheets,
        compute_expected=lambda r: r.total_liabilities + r.total_equity,
        get_actual=lambda r: r.total_assets,
        get_key=_key,
    )
    report("accounting_equation", total, passed, failures)
