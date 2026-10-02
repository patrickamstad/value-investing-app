import pytest
from quickfs_dj.models import CashFlowStatementAnnual
from tests.fundamentals_consistency.helpers import check_identity, report

pytestmark = pytest.mark.django_db(databases=["default"])


def _key(r):
    return r.qfs_symbol_id, r.period_end_date


def test_cf_cfo():
    """net_income + da + stock_comp + change_in_wc + other_noncash = cf_cfo (guaranteed by construction)"""
    cash_flows = CashFlowStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        cash_flows,
        compute_expected=lambda r: (
            (r.cfo_net_income or 0)
            + (r.cfo_da or 0)
            + (r.cfo_stock_comp or 0)
            + (r.cfo_change_in_working_capital or 0)
            + (r.cfo_other_noncash_items or 0)
            if r.cf_cfo is not None else None
        ),
        get_actual=lambda r: r.cf_cfo,
        get_key=_key,
    )
    report("cf_cfo", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_cf_cfi():
    """ppe_net + investment_net + cfi_other = cf_cfi (guaranteed by construction)"""
    cash_flows = CashFlowStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        cash_flows,
        compute_expected=lambda r: (
            (r.cfi_ppe_net or 0)
            + (r.cfi_investment_net or 0)
            + (r.cfi_other or 0)
            if r.cf_cfi is not None else None
        ),
        get_actual=lambda r: r.cf_cfi,
        get_key=_key,
    )
    report("cf_cfi", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_cf_cff():
    """common_stock_net + debt_net + dividend_paid + cff_other = cf_cff (guaranteed by construction)"""
    cash_flows = CashFlowStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        cash_flows,
        compute_expected=lambda r: (
            (r.cff_common_stock_net or 0)
            + (r.cff_debt_net or 0)
            + (r.cff_dividend_paid or 0)
            + (r.cff_other or 0)
            if r.cf_cff is not None else None
        ),
        get_actual=lambda r: r.cf_cff,
        get_key=_key,
    )
    report("cf_cff", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_net_change_in_cash():
    """cf_cfo + cf_cfi + cf_cff + cf_forex = cf_net_change_in_cash (guaranteed by construction)"""
    cash_flows = CashFlowStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        cash_flows,
        compute_expected=lambda r: (
            (r.cf_cfo or 0) + (r.cf_cfi or 0) + (r.cf_cff or 0) + (r.cf_forex or 0)
            if r.cf_net_change_in_cash is not None else None
        ),
        get_actual=lambda r: r.cf_net_change_in_cash,
        get_key=_key,
    )
    report("net_change_in_cash", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"
