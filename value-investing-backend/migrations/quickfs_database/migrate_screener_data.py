import psycopg2
from psycopg2.extras import execute_values, DictCursor
from datetime import date
from dateutil.relativedelta import relativedelta
import os
from dotenv import load_dotenv
load_dotenv()
# -----------------------------
# Configuration
# -----------------------------


CUTOFF_DATE = date.today() - relativedelta(months=8)
BATCH_SIZE = 200



#keys of the screener mapping corresponds to fields in the different tables (BalanceSheet, IncomeStatement), values correspond to columns in the ScreenerData table
#this mapping is needed because for example the BalanceSheetAnnual and BalanceSheetQuarterly have same columns (cash_and_equiv, st_investments, etc.) --> we need different names for these in the screener data table
SCREENERDATA_MAPPING = {
    # TradedCompany
    "TradedCompanies" : 
        {
        "ticker": "ticker",
        "exchange": "exchange",
        "name": "name",
        "industry": "industry",
        "last_close_price" : "last_close_price"
        },

    # Valuation
    "Valuation" : 
        {
        "epv_business": "epv_business",
        "epv_per_share": "epv_per_share",
        "epv_business_ttm": "epv_business_ttm",
        "epv_per_share_ttm": "epv_per_share_ttm",
        "penman_equity": "penman_equity",
        "penman_per_share": "penman_per_share",
        "penman_g": "penman_g",
        "rnoa": "rnoa_y",
        "penman_equity_ttm": "penman_equity_ttm",
        "penman_per_share_ttm": "penman_per_share_ttm",
        "penman_g_ttm": "penman_g_ttm",
        "rnoa_ttm": "rnoa_ttm",
        "price": "price",
        },

    # IncomeStatementAnnual
    "IncomeAnnual" : 
        {
        "revenue": "revenue_y",
        "cogs": "cogs_y",
        "gross_profit": "gross_profit_y",
        "sga": "sga_y",
        "rnd": "rnd_y",
        "special_charges": "special_charges_y",
        "other_opex": "other_opex_y",
        "total_opex": "total_opex_y",
        "operating_income": "operating_income_y",
        "interest_income": "interest_income_y",
        "interest_expense": "interest_expense_y",
        "net_interest_income_normal": "net_interest_income_normal_y",
        "other_nonoperating_income": "other_nonoperating_income_y",
        "pretax_income": "pretax_income_y",
        "income_tax": "income_tax_y",
        "net_income_continuing": "net_income_continuing_y",
        "net_income_discontinued": "net_income_discontinued_y",
        "income_allocated_to_minority_interest": "income_allocated_to_minority_interest_y",
        "other_income_statement_items": "other_income_statement_items_y",
        "net_income": "net_income_y",
        "preferred_dividends": "preferred_dividends_y",
        "net_income_available_to_shareholders": "net_income_available_to_shareholders_y",
        "eps_basic": "eps_basic_y",
        "eps_diluted": "eps_diluted_y",
        "shares_basic": "shares_basic_y",
        "shares_diluted": "shares_diluted_y",
        "shares_eop": "shares_eop_y",
        "shares_eop_change": "shares_eop_change_y",

        # "qfs_symbol_id" : "qfs_symbol_id",
        },

    # BalanceSheetAnnual
    "BalanceAnnual" : 
        {
        "cash_and_equiv": "cash_and_equiv_y",
        "st_investments": "st_investments_y",
        "receivables": "receivables_y",
        "inventories": "inventories_y",
        "other_current_assets": "other_current_assets_y",
        "total_current_assets": "total_current_assets_y",
        "equity_and_other_investments": "equity_and_other_investments_y",
        "ppe_gross": "ppe_gross_y",
        "accumulated_depreciation": "accumulated_depreciation_y",
        "ppe_net": "ppe_net_y",
        "intangible_assets": "intangible_assets_y",
        "goodwill": "goodwill_y",
        "other_lt_assets": "other_lt_assets_y",
        "total_assets": "total_assets_y",
        "accounts_payable": "accounts_payable_y",
        "tax_payable": "tax_payable_y",
        "current_accrued_liabilities": "current_accrued_liabilities_y",
        "st_debt": "st_debt_y",
        "current_deferred_revenue": "current_deferred_revenue_y",
        "current_deferred_tax_liability": "current_deferred_tax_liability_y",
        "current_capital_leases": "current_capital_leases_y",
        "other_current_liabilities": "other_current_liabilities_y",
        "total_current_liabilities": "total_current_liabilities_y",
        "lt_debt": "lt_debt_y",
        "noncurrent_capital_leases": "noncurrent_capital_leases_y",
        "pension_liabilities": "pension_liabilities_y",
        "noncurrent_deferred_revenue": "noncurrent_deferred_revenue_y",
        "other_lt_liabilities": "other_lt_liabilities_y",
        "total_liabilities": "total_liabilities_y",
        "common_stock": "common_stock_y",
        "preferred_stock": "preferred_stock_y",
        "retained_earnings": "retained_earnings_y",
        "aoci": "aoci_y",
        "apic": "apic_y",
        "treasury_stock": "treasury_stock_y",
        "other_equity": "other_equity_y",
        "minority_interest_liability": "minority_interest_liability_y",
        "total_equity": "total_equity_y",
        "total_liabilities_and_equity": "total_liabilities_and_equity_y",
        },

    # BalanceSheetQuarter (corrected)
    "BalanceQuarter" : 
        {
        "cash_and_equiv": "cash_and_equiv_q",
        "st_investments": "st_investments_q",
        "receivables": "receivables_q",
        "inventories": "inventories_q",
        "other_current_assets": "other_current_assets_q",
        "total_current_assets": "total_current_assets_q",
        "equity_and_other_investments": "equity_and_other_investments_q",
        "ppe_gross": "ppe_gross_q",
        "accumulated_depreciation": "accumulated_depreciation_q",
        "ppe_net": "ppe_net_q",
        "intangible_assets": "intangible_assets_q",
        "goodwill": "goodwill_q",
        "other_lt_assets": "other_lt_assets_q",
        "total_assets": "total_assets_q",
        "accounts_payable": "accounts_payable_q",
        "tax_payable": "tax_payable_q",
        "current_accrued_liabilities": "current_accrued_liabilities_q",
        "st_debt": "st_debt_q",
        "current_deferred_revenue": "current_deferred_revenue_q",
        "current_deferred_tax_liability": "current_deferred_tax_liability_q",
        "current_capital_leases": "current_capital_leases_q",
        "other_current_liabilities": "other_current_liabilities_q",
        "total_current_liabilities": "total_current_liabilities_q",
        "lt_debt": "lt_debt_q",
        "noncurrent_capital_leases": "noncurrent_capital_leases_q",
        "pension_liabilities": "pension_liabilities_q",
        "noncurrent_deferred_revenue": "noncurrent_deferred_revenue_q",
        "other_lt_liabilities": "other_lt_liabilities_q",
        "total_liabilities": "total_liabilities_q",
        "common_stock": "common_stock_q",
        "preferred_stock": "preferred_stock_q",
        "retained_earnings": "retained_earnings_q",
        "aoci": "aoci_q",
        "apic": "apic_q",
        "treasury_stock": "treasury_stock_q",
        "other_equity": "other_equity_q",
        },
    # CashFlowAnnual (CFO, CFI, CFF)
    "CashFlowAnnual" : 
        {
        "cfo_net_income": "cfo_net_income_y",
        "cfo_da": "cfo_da_y",
        "cfo_receivables": "cfo_receivables_y",
        "cfo_inventory": "cfo_inventory_y",
        "cfo_prepaid_expenses": "cfo_prepaid_expenses_y",
        "cfo_other_working_capital": "cfo_other_working_capital_y",
        "cfo_change_in_working_capital": "cfo_change_in_working_capital_y",
        "cfo_deferred_tax": "cfo_deferred_tax_y",
        "cfo_stock_comp": "cfo_stock_comp_y",
        "cfo_other_noncash_items": "cfo_other_noncash_items_y",
        "cf_cfo": "cf_cfo_y",
        "cfi_ppe_purchases": "cfi_ppe_purchases_y",
        "cfi_ppe_sales": "cfi_ppe_sales_y",
        "cfi_ppe_net": "cfi_ppe_net_y",
        "cfi_acquisitions": "cfi_acquisitions_y",
        "cfi_divestitures": "cfi_divestitures_y",
        "cfi_acquisitions_net": "cfi_acquisitions_net_y",
        "cfi_investment_purchases": "cfi_investment_purchases_y",
        "cfi_investment_sales": "cfi_investment_sales_y",
        "cfi_investment_net": "cfi_investment_net_y",
        "cfi_intangibles_net": "cfi_intangibles_net_y",
        "cfi_other": "cfi_other_y",
        "cf_cfi": "cf_cfi_y",
        "cff_common_stock_issued": "cff_common_stock_issued_y",
        "cff_common_stock_repurchased": "cff_common_stock_repurchased_y",
        "cff_common_stock_net": "cff_common_stock_net_y",
        "cff_pfd_issued": "cff_pfd_issued_y",
        "cff_pfd_repurchased": "cff_pfd_repurchased_y",
        "cff_pfd_net": "cff_pfd_net_y",
        "cff_debt_issued": "cff_debt_issued_y",
        "cff_debt_repaid": "cff_debt_repaid_y",
        "cff_debt_net": "cff_debt_net_y",
        "cff_dividend_paid": "cff_dividend_paid_y",
        "cff_other": "cff_other_y",
        "cf_cff": "cf_cff_y",
        },
    # KeyRatiosQuarter
    "KeyRatiosQuarter" : 
    {
    "market_cap": "market_cap_q",
    "period_end_price": "period_end_price_q",
    "enterprise_value": "enterprise_value_q",
    "book_value": "book_value_q",
    "tangible_book_value": "tangible_book_value_q",
    "price_to_earnings": "price_to_earnings_q",
    "price_to_book": "price_to_book_q",
    "price_to_sales": "price_to_sales_q",
    "price_to_tangible_book": "price_to_tangible_book_q",
    "price_to_fcf": "price_to_fcf_q",
    "price_to_pretax_income": "price_to_pretax_income_q",
    "enterprise_value_to_earnings": "enterprise_value_to_earnings_q",
    "enterprise_value_to_book": "enterprise_value_to_book_q",
    "enterprise_value_to_tangible_book": "enterprise_value_to_tangible_book_q",
    "enterprise_value_to_sales": "enterprise_value_to_sales_q",
    "enterprise_value_to_fcf": "enterprise_value_to_fcf_q",
    "enterprise_value_to_pretax_income": "enterprise_value_to_pretax_income_q",
    "ebitda": "ebitda_q",
    "capex": "capex_q",
    "fcf": "fcf_q",
    "earning_assets": "earning_assets_q",
    "policy_revenue": "policy_revenue_q",
    "underwriting_profit": "underwriting_profit_q",
    "dividends": "dividends_q",
    "payout_ratio": "payout_ratio_q",
    "income_tax_rate": "income_tax_rate_q",
    "net_debt": "net_debt_q",
    "gross_margin": "gross_margin_q",
    "ebitda_margin": "ebitda_margin_q",
    "operating_margin": "operating_margin_q",
    "pretax_margin": "pretax_margin_q",
    "net_income_margin": "net_income_margin_q",
    "fcf_margin": "fcf_margin_q",
    "net_interest_margin": "net_interest_margin_q",
    "underwriting_margin": "underwriting_margin_q",
    "roe": "roe_q",
    "roa": "roa_q",
    "roic": "roic_q",
    "roic_legacy": "roic_legacy_q",
    "roce": "roce_q",
    "rotce": "rotce_q",
    "roi": "roi_q",
    "debt_to_equity": "debt_to_equity_q",
    "equity_to_assets": "equity_to_assets_q",
    "debt_to_assets": "debt_to_assets_q",
    "assets_to_equity": "assets_to_equity_q",
    "current_ratio": "current_ratio_q",
    "earning_assets_to_equity": "earning_assets_to_equity_q",
    "loans_to_deposits": "loans_to_deposits_q",
    "loan_loss_reserve_to_loans": "loan_loss_reserve_to_loans_q",
    "revenue_per_share": "revenue_per_share_q",
    "ebitda_per_share": "ebitda_per_share_q",
    "operating_income_per_share": "operating_income_per_share_q",
    "pretax_income_per_share": "pretax_income_per_share_q",
    "fcf_per_share": "fcf_per_share_q",
    "book_value_per_share": "book_value_per_share_q",
    "tangible_book_per_share": "tangible_book_per_share_q",
    "premiums_per_share": "premiums_per_share_q",
    "revenue_growth": "revenue_growth_q",
    "gross_profit_growth": "gross_profit_growth_q",
    "ebitda_growth": "ebitda_growth_q",
    "operating_income_growth": "operating_income_growth_q",
    "pretax_income_growth": "pretax_income_growth_q",
    "net_income_growth": "net_income_growth_q",
    "eps_diluted_growth": "eps_diluted_growth_q",
    "shares_diluted_growth": "shares_diluted_growth_q",
    "shares_eop_growth": "shares_eop_growth_q",
    "cash_and_equiv_growth": "cash_and_equiv_growth_q",
    "ppe_growth": "ppe_growth_q",
    "total_assets_growth": "total_assets_growth_q",
    "total_equity_growth": "total_equity_growth_q",
    "cfo_growth": "cfo_growth_q",
    "capex_growth": "capex_growth_q",
    "fcf_growth": "fcf_growth_q",
    "revenue_cagr_10": "revenue_cagr_10_q",
    "eps_diluted_cagr_10": "eps_diluted_cagr_10_q",
    "total_assets_cagr_10": "total_assets_cagr_10_q",
    "total_equity_cagr_10": "total_equity_cagr_10_q",
    "cf_cfo_cagr_10": "cf_cfo_cagr_10_q",
    "fcf_cagr_10": "fcf_cagr_10_q",
    },
    # KeyRatiosAnnual
    "KeyRatiosAnnual" : 
        {
        "market_cap": "market_cap_y",
        "period_end_price": "period_end_price_y",
        "enterprise_value": "enterprise_value_y",
        "book_value": "book_value_y",
        "tangible_book_value": "tangible_book_value_y",
        "price_to_earnings": "price_to_earnings_y",
        "price_to_book": "price_to_book_y",
        "price_to_sales": "price_to_sales_y",
        "price_to_tangible_book": "price_to_tangible_book_y",
        "price_to_fcf": "price_to_fcf_y",
        "price_to_pretax_income": "price_to_pretax_income_y",
        "enterprise_value_to_earnings": "enterprise_value_to_earnings_y",
        "enterprise_value_to_book": "enterprise_value_to_book_y",
        "enterprise_value_to_tangible_book": "enterprise_value_to_tangible_book_y",
        "enterprise_value_to_sales": "enterprise_value_to_sales_y",
        "enterprise_value_to_fcf": "enterprise_value_to_fcf_y",
        "enterprise_value_to_pretax_income": "enterprise_value_to_pretax_income_y",
        "ebitda": "ebitda_y",
        "capex": "capex_y",
        "fcf": "fcf_y",
        "earning_assets": "earning_assets_y",
        "policy_revenue": "policy_revenue_y",
        "underwriting_profit": "underwriting_profit_y",
        "dividends": "dividends_y",
        "payout_ratio": "payout_ratio_y",
        "income_tax_rate": "income_tax_rate_y",
        "net_debt": "net_debt_y",
        "gross_margin": "gross_margin_y",
        "ebitda_margin": "ebitda_margin_y",
        "operating_margin": "operating_margin_y",
        "pretax_margin": "pretax_margin_y",
        "net_income_margin": "net_income_margin_y",
        "fcf_margin": "fcf_margin_y",
        "net_interest_margin": "net_interest_margin_y",
        "underwriting_margin": "underwriting_margin_y",
        "roe": "roe_y",
        "roa": "roa_y",
        "roic": "roic_y",
        "roic_legacy": "roic_legacy_y",
        "roce": "roce_y",
        "rotce": "rotce_y",
        "roi": "roi_y",
        "debt_to_equity": "debt_to_equity_y",
        "debt_to_assets": "debt_to_assets_y",
        "equity_to_assets": "equity_to_assets_y",
        "assets_to_equity": "assets_to_equity_y",
        "current_ratio": "current_ratio_y",
        "earning_assets_to_equity": "earning_assets_to_equity_y",
        "loans_to_deposits": "loans_to_deposits_y",
        "loan_loss_reserve_to_loans": "loan_loss_reserve_to_loans_y",
        "revenue_per_share": "revenue_per_share_y",
        "ebitda_per_share": "ebitda_per_share_y",
        "operating_income_per_share": "operating_income_per_share_y",
        "pretax_income_per_share": "pretax_income_per_share_y",
        "fcf_per_share": "fcf_per_share_y",
        "book_value_per_share": "book_value_per_share_y",
        "tangible_book_per_share": "tangible_book_per_share_y",
        "premiums_per_share": "premiums_per_share_y",
        "revenue_growth": "revenue_growth_y",
        "gross_profit_growth": "gross_profit_growth_y",
        "ebitda_growth": "ebitda_growth_y",
        "operating_income_growth": "operating_income_growth_y",
        "pretax_income_growth": "pretax_income_growth_y",
        "net_income_growth": "net_income_growth_y",
        "eps_diluted_growth": "eps_diluted_growth_y",
        "shares_diluted_growth": "shares_diluted_growth_y",
        "shares_eop_growth": "shares_eop_growth_y",
        "cash_and_equiv_growth": "cash_and_equiv_growth_y",
        "ppe_growth": "ppe_growth_y",
        "total_assets_growth": "total_assets_growth_y",
        "total_equity_growth": "total_equity_growth_y",
        "cfo_growth": "cfo_growth_y",
        "capex_growth": "capex_growth_y",
        "fcf_growth": "fcf_growth_y",
        "revenue_cagr_10": "revenue_cagr_10_y",
        "eps_diluted_cagr_10": "eps_diluted_cagr_10_y",
        "total_assets_cagr_10": "total_assets_cagr_10_y",
        "total_equity_cagr_10": "total_equity_cagr_10_y",
        "cf_cfo_cagr_10": "cf_cfo_cagr_10_y",
        "fcf_cagr_10": "fcf_cagr_10_y",
        }
}

# -----------------------------
# Helper functions
# -----------------------------
def fetch_latest_records(cur, table_name, date_column):
    """
    Fetch the latest record per qfs_symbol_id from a table.
    """
    cur.execute(f"""
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER(PARTITION BY qfs_symbol_id ORDER BY {date_column} DESC) AS rn
            FROM {table_name}
        )
        SELECT * FROM ranked WHERE rn = 1;
    """)
    rows = cur.fetchall()
    # Convert to dict keyed by qfs_symbol_id for fast lookup
    return {row['qfs_symbol_id']: dict(row) for row in rows}


def get_updatable_columns(cur, table_name, pk_column="id", exclude_columns=None):
    """
    Return a list of updatable column names for a given table.
    Excludes primary key, auto-increment, and any user-specified exclusions.
    """
    if exclude_columns is None:
        exclude_columns = []

    # Query information_schema for all columns
    cur.execute("""
        SELECT column_name, is_identity
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))

    columns = []
    for col, is_identity in cur.fetchall():
        if col == pk_column:   # skip PK
            continue
        if is_identity == "YES":  # skip auto-increment / identity columns
            continue
        if col in exclude_columns:  # skip any explicitly excluded columns
            continue
        columns.append(col)

    return columns

# Share counts live in the same tables as revenue/net_income/etc. but aren't monetary
# amounts - never FX-convert these even when the rest of the table gets converted.
NON_MONETARY_COLUMNS = {"shares_basic", "shares_diluted", "shares_eop", "shares_eop_change"}

# Only these source tables hold raw fundamentals in reporting_currency. TradedCompanies
# is company info (already trading-currency by definition), Valuation is already computed
# in trading currency upstream (see migrate_valuation_data.py's fx CTE), and KeyRatiosAnnual/
# KeyRatiosQuarter are frozen legacy QuickFS-era data with no active writer (see the
# ScreenerData model docstring) - we do not attempt to currency-convert those.
FUNDAMENTALS_TABLES = {"IncomeAnnual", "BalanceAnnual", "BalanceQuarter", "CashFlowAnnual"}


def map_columns(row, table_name, fx_rate=1.0):
    """fx_rate: units of trading currency per 1 unit of reporting currency for this
    company (see main() - looked up once per company from quickfs_dj_fxrate)."""
    mapped_row = {}
    mapping = SCREENERDATA_MAPPING[table_name]
    apply_fx = fx_rate != 1.0 and table_name in FUNDAMENTALS_TABLES
    for col, value in row.items():
        if col in mapping:
            if apply_fx and col not in NON_MONETARY_COLUMNS and isinstance(value, (int, float)):
                value = value * fx_rate
            mapped_row.update({mapping[col] : value})
        # else:
        #     print(f"Warning: No mapping for column '{col}', table: {table_name}")
    return mapped_row

# -----------------------------
# Main script
# -----------------------------
def main():
    # Connect to DB
    conn = psycopg2.connect(host=os.environ['DB_HOST'], database=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD'], port=os.environ['DB_PORT'])
    cur = conn.cursor(cursor_factory=DictCursor)

    print("Fetching traded companies...")
    #cur.execute("SELECT * FROM quickfs_dj_tradedcompanies where qfs_symbol in ('YRD:US', 'META:US');")
    cur.execute("SELECT * FROM quickfs_dj_tradedcompanies;")

    companies = cur.fetchall()

    print("Fetching latest valuation data...")
    valuations = fetch_latest_records(cur, "quickfs_dj_valuation", "valuation_date")

    print("Fetching latest income statements...")
    income_statements = fetch_latest_records(cur, "quickfs_dj_incomestatementannual", "period_end_date")

    print("Fetching latest balance sheets (annual)...")
    balance_sheet_annual = fetch_latest_records(cur, "quickfs_dj_balancesheetannual", "period_end_date")

    print("Fetching latest balance sheets (quarter)...")
    balance_sheet_quarter = fetch_latest_records(cur, "quickfs_dj_balancesheetquarter", "period_end_date")

    print("Fetching latest cash flow statements...")
    cash_flow_annual = fetch_latest_records(cur, "quickfs_dj_cashflowstatementannual", "period_end_date")

    print("Fetching latest key ratios (quarter)...")
    key_ratios_quarter = fetch_latest_records(cur, "quickfs_dj_keyratiosquarter", "period_end_date")

    print("Fetching latest key ratios (annual)...")
    key_ratios_annual = fetch_latest_records(cur, "quickfs_dj_keyratiosannual", "period_end_date")

    print("Fetching FX rates...")
    cur.execute("SELECT from_currency, to_currency, rate FROM quickfs_dj_fxrate;")
    fx_rates = {(r['from_currency'], r['to_currency']): r['rate'] for r in cur.fetchall()}

    screener_data_list = []

    print("Building denormalized screener data...")
    for comp in companies:
        qfs_symbol = comp['qfs_symbol']
        trading_currency = comp.get('currency')

        # Skip if the most recent quarterly filing is older than 8 months. Originally
        # gated on key_ratios_quarter (the last table populated by the old QuickFS
        # pipeline, so its freshness was a proxy for "the whole pipeline succeeded for
        # this company"), but KeyRatiosAnnual/KeyRatiosQuarter have had no writer since
        # the move to EODHD and are permanently empty now - gate on balance_sheet_quarter
        # instead, which the live EODHD pipeline actually populates every run.
        bs_q = balance_sheet_quarter.get(qfs_symbol)
        if not bs_q or bs_q['period_end_date'] < CUTOFF_DATE:
            continue

        # Determine the FX factor to convert this company's fundamentals (filed in
        # reporting_currency) into its trading currency (= last_close_price's currency).
        # Defaults to 1.0 - the common case - when they already match, reporting_currency
        # isn't populated yet, or no FxRate row exists for the pair (logged below so a
        # missing rate is visible rather than silently wrong).
        fx_rate = 1.0
        income_stmt = income_statements.get(qfs_symbol)
        reporting_currency = income_stmt.get('reporting_currency') if income_stmt else None
        if reporting_currency and trading_currency and reporting_currency != trading_currency:
            pair = (reporting_currency, trading_currency)
            if pair in fx_rates:
                fx_rate = fx_rates[pair]
            else:
                print(f"[WARN] {qfs_symbol}: no FxRate for {reporting_currency}->{trading_currency}, using 1.0")

        # Merge all available data into one row
        row = {
            'qfs_symbol_id': qfs_symbol,
            'ticker': comp.get('ticker'),
            'exchange': comp.get('exchange'),
            'name': comp.get('name'),
            'industry': comp.get('industry'),
            'last_close_price' : comp.get('last_close_price'),
            'currency': trading_currency,
        }

        # Merge data from other tables if available
        for source in [(valuations, "Valuation"), (income_statements, "IncomeAnnual"), (balance_sheet_annual, "BalanceAnnual"),
                       (balance_sheet_quarter, "BalanceQuarter"), (cash_flow_annual, "CashFlowAnnual"),
                       (key_ratios_quarter, "KeyRatiosQuarter"), (key_ratios_annual, "KeyRatiosAnnual")]:
            data = source[0].get(qfs_symbol)

            """
            we need to adjust two thing: We already need to use correct column values here otherwise we will overwrite them: For example balance sheet quarter and annual both have the field cash_and_equiv
            """

            #remove id and rn key

            if data:
                data = map_columns(data, table_name=source[1], fx_rate=fx_rate)
                row.update(data)

        screener_data_list.append(row)

    if not screener_data_list:
        print("No data to insert. Exiting.")
        return

    print(f"Inserting/updating {len(screener_data_list)} records into screenerdata...")

    # Get all column names that should be inserted
    #columns = list(screener_data_list[0].keys())
    columns = get_updatable_columns(cur=cur, table_name="quickfs_dj_screenerdata")

    #only keep values which are part of updatable columns
    values = [[row.get(col) for col in columns] for row in screener_data_list]

    insert_sql = f"""
    INSERT INTO quickfs_dj_screenerdata ({', '.join(columns)})
    VALUES %s
    ON CONFLICT (qfs_symbol_id)
    DO UPDATE SET {', '.join(f"{col}=EXCLUDED.{col}" for col in columns)}
    """

    execute_values(cur, insert_sql, values, page_size=BATCH_SIZE)
    conn.commit()

    print("Done!")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()