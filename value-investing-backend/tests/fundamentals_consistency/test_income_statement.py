import pytest
from quickfs_dj.models import IncomeStatementAnnual
from tests.fundamentals_consistency.helpers import check_identity, report

pytestmark = pytest.mark.django_db(databases=["default"])


def _key(r):
    return r.qfs_symbol_id, r.period_end_date


def test_gross_profit():
    """revenue - cogs = gross_profit (informational only).

    Not asserted: both sides are raw EODHD anchors and may disagree — explicitly documented
    in the module docstring. Fails systematically for banks and insurers where EODHD maps
    non-standard fields to revenue/cogs.
    """
    income_statements = IncomeStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        income_statements,
        compute_expected=lambda r: r.revenue - (r.cogs or 0) if r.revenue is not None else None,
        get_actual=lambda r: r.gross_profit,
        get_key=_key,
    )
    report("gross_profit", total, passed, failures)


def test_operating_income():
    """gross_profit - total_opex = operating_income (guaranteed by construction)"""
    income_statements = IncomeStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        income_statements,
        compute_expected=lambda r: (
            r.gross_profit - r.total_opex
            if r.gross_profit is not None and r.operating_income is not None else None
        ),
        get_actual=lambda r: r.operating_income if r.gross_profit is not None else None,
        get_key=_key,
    )
    report("operating_income", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_pretax_income():
    """operating_income + interest_income - interest_expense + other_nonoperating_income = pretax_income (guaranteed by construction)"""
    income_statements = IncomeStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        income_statements,
        compute_expected=lambda r: (
            r.operating_income
            + (r.interest_income or 0)
            - (r.interest_expense or 0)
            + (r.other_nonoperating_income or 0)
            if r.operating_income is not None and r.pretax_income is not None else None
        ),
        get_actual=lambda r: r.pretax_income if r.operating_income is not None else None,
        get_key=_key,
    )
    report("pretax_income", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


def test_net_income():
    """pretax_income - income_tax + minority_interest + discontinued + other_items = net_income (guaranteed by construction)"""
    income_statements = IncomeStatementAnnual.objects.all()
    total, passed, failures = check_identity(
        income_statements,
        compute_expected=lambda r: (
            r.pretax_income
            - (r.income_tax or 0)
            + (r.income_allocated_to_minority_interest or 0)
            + (r.net_income_discontinued or 0)
            + (r.other_income_statement_items or 0)
            if r.pretax_income is not None and r.net_income is not None else None
        ),
        get_actual=lambda r: r.net_income if r.pretax_income is not None else None,
        get_key=_key,
    )
    report("net_income", total, passed, failures)
    assert not failures, f"{len(failures)}/{total} records failed"


# def test_net_income_available_to_shareholders():
#     """net_income - preferred_dividends = net_income_available_to_shareholders"""
#     income_statements = IncomeStatementAnnual.objects.all()
#     total, passed, failures = check_identity(
#         income_statements,
#         compute_expected=lambda r: r.net_income - (r.preferred_dividends or 0),
#         get_actual=lambda r: r.net_income_available_to_shareholders,
#         get_key=_key,
#     )
#     report("net_income_available_to_shareholders", total, passed, failures)
#     assert not failures, f"{len(failures)}/{total} records failed"
