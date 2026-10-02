from django.db import models
import hashlib

def generate_unique_id(model_name, field_name):
    """Generate a unique, consistent ID based on model and field names."""
    unique_str = f"{model_name}.{field_name}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:10]  # Short, consistent ID

# Create your models here.
class TradedCompanies(models.Model):
    ticker = models.CharField(max_length=30, db_index=True)
    qfs_symbol = models.CharField(max_length=30, unique=True, verbose_name="QFS Symbol")
    exchange = models.CharField(max_length=30, verbose_name="Exchange")
    name = models.CharField(max_length=500, verbose_name="Name")
    company_type = models.CharField(max_length=300, null=True, blank=True, verbose_name="Company Type")
    currency = models.CharField(max_length=30, null=True, blank=True, verbose_name="Currency")
    industry = models.CharField(max_length=300, null=True, blank=True, verbose_name="Industry")
    has_new_financials = models.BooleanField(null=True, blank=True, default=True)
    last_close_price = models.FloatField(null=True, blank=True)

    column_metadata = {
        'qfs_symbol' : 'comp',
        'exchange' : 'comp',
        'name' : 'comp',
        'company_type' : 'comp',
        'currency' : 'comp',
        'industry' : 'comp',
    }

class FxRate(models.Model):
    """
    One row per currency pair, always in the direction we actually need:
    from_currency = a fundamentals row's reporting_currency (what was filed)
    to_currency   = TradedCompanies.currency (what the stock trades/prices in)
    rate          = units of to_currency per 1 unit of from_currency

    Example: YRD.US files its financials in CNY but trades in USD.
        from_currency = "CNY", to_currency = "USD", rate = 0.14
    To convert a filed amount into trading currency: amount_to = amount_from * rate.
    e.g. revenue of CNY 5,572,209,105 -> 5,572,209,105 * 0.14 ~= USD 780,109,275.

    Only this one direction is ever looked up (every consumer converts
    reporting_currency -> trading_currency, never the reverse), so we only
    fetch/store that direction. If some future use case ever needed the
    reverse (USD -> CNY), compute it as 1/rate from this same row rather
    than storing and refreshing a second, independently-drifting row.
    """
    from_currency = models.CharField(max_length=10, db_index=True)
    to_currency = models.CharField(max_length=10, db_index=True)
    rate = models.FloatField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('from_currency', 'to_currency')

class Valuation(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    valuation_date = models.DateField(db_index=True)
    epv_business = models.FloatField(null=True, blank=True)
    epv_per_share = models.FloatField(null=True, blank=True)
    epv_business_ttm = models.FloatField(null=True, blank=True)
    epv_per_share_ttm = models.FloatField(null=True, blank=True)
    penman_equity = models.FloatField(null=True, blank=True)
    penman_per_share = models.FloatField(null=True, blank=True)
    penman_g = models.FloatField(null=True, blank=True) #implied growth rate
    rnoa = models.FloatField(null=True, blank=True)
    penman_equity_ttm = models.FloatField(null=True, blank=True)
    penman_per_share_ttm = models.FloatField(null=True, blank=True)
    penman_g_ttm = models.FloatField(null=True, blank=True) #implied growth rate
    rnoa_ttm = models.FloatField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'valuation_date')

class EPSForecasts(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    year = models.IntegerField(db_index=True)
    low = models.FloatField(null=True, blank=True)
    avg = models.FloatField(null=True, blank=True)
    high = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'year')

#this model only contains the latest/most up-to-date income statement. This means for each ticker we only have one entry (the one with max(period_end_date). This model will be used for the screener functionality --> queries run much faster on this smaller table)
class LatestIncomeStatementAnnual(models.Model):
    #OneToOneField enforces that for each ticker symbol you have at max one entry
    qfs_symbol = models.OneToOneField(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    revenue = models.FloatField(null=True, blank=True)
    cogs = models.FloatField(null=True, blank=True)
    gross_profit = models.FloatField(null=True, blank=True)
    sga = models.FloatField(null=True, blank=True)
    rnd = models.FloatField(null=True, blank=True)
    special_charges = models.FloatField(null=True, blank=True)
    other_opex = models.FloatField(null=True, blank=True)
    total_opex = models.FloatField(null=True, blank=True)
    operating_income = models.FloatField(null=True, blank=True, db_index=True)
    interest_income = models.FloatField(null=True, blank=True)
    interest_expense = models.FloatField(null=True, blank=True)
    net_interest_income_normal = models.FloatField(null=True, blank=True)
    other_nonoperating_income = models.FloatField(null=True, blank=True)
    pretax_income = models.FloatField(null=True, blank=True)
    income_tax = models.FloatField(null=True, blank=True)
    net_income_continuing = models.FloatField(null=True, blank=True)
    net_income_discontinued = models.FloatField(null=True, blank=True)
    income_allocated_to_minority_interest = models.FloatField(null=True, blank=True)
    other_income_statement_items = models.FloatField(null=True, blank=True)
    net_income = models.FloatField(null=True, blank=True)
    preferred_dividends = models.FloatField(null=True, blank=True)
    net_income_available_to_shareholders = models.FloatField(null=True, blank=True)
    eps_basic = models.FloatField(null=True, blank=True)
    eps_diluted = models.FloatField(null=True, blank=True)
    shares_basic = models.FloatField(null=True, blank=True)
    shares_diluted = models.FloatField(null=True, blank=True)
    shares_eop = models.FloatField(null=True, blank=True)
    shares_eop_change = models.FloatField(null=True, blank=True)
    premiums_earned = models.FloatField(null=True, blank=True)
    net_investment_income = models.FloatField(null=True, blank=True)
    fees_and_other_income = models.FloatField(null=True, blank=True)
    net_policyholder_claims_expense = models.FloatField(null=True, blank=True)
    policy_acquisition_expense = models.FloatField(null=True, blank=True)
    interest_expense_insurance = models.FloatField(null=True, blank=True)
    total_interest_income = models.FloatField(null=True, blank=True)
    total_interest_expense = models.FloatField(null=True, blank=True)
    net_interest_income = models.FloatField(null=True, blank=True)
    total_noninterest_revenue = models.FloatField(null=True, blank=True)
    credit_losses_provision = models.FloatField(null=True, blank=True)
    net_interest_income_after_credit_losses_provision = models.FloatField(null=True, blank=True)
    total_noninterest_expense = models.FloatField(null=True, blank=True)
    da_income_statement_supplemental = models.FloatField(null=True, blank=True)

class IncomeStatementAnnual(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=10, null=True, blank=True, verbose_name="Reporting Currency")
    revenue = models.FloatField(null=True, blank=True, verbose_name="Revenue")
    cogs = models.FloatField(null=True, blank=True, verbose_name="Cost of Goods Sold (COGS)")
    gross_profit = models.FloatField(null=True, blank=True, verbose_name="Gross Profit")
    sga = models.FloatField(null=True, blank=True, verbose_name="Selling General and Administratives (SG&A)")
    rnd = models.FloatField(null=True, blank=True, verbose_name="Research and Development (R&D)")
    special_charges = models.FloatField(null=True, blank=True, verbose_name="Special Charges")
    other_opex = models.FloatField(null=True, blank=True, verbose_name="Other Operating Expenses")
    total_opex = models.FloatField(null=True, blank=True, verbose_name="Total Operating Expenses")
    operating_income = models.FloatField(null=True, blank=True, db_index=True, verbose_name="Operating Income")
    interest_income = models.FloatField(null=True, blank=True, verbose_name="Interest Income")
    interest_expense = models.FloatField(null=True, blank=True, verbose_name="Interest Expense")
    net_interest_income_normal = models.FloatField(null=True, blank=True, verbose_name="Net Interest Income Normal")
    other_nonoperating_income = models.FloatField(null=True, blank=True, verbose_name="Other Non-Operating Income")
    pretax_income = models.FloatField(null=True, blank=True, verbose_name="Pretax Income")
    income_tax = models.FloatField(null=True, blank=True, verbose_name="Income Tax")
    net_income_continuing = models.FloatField(null=True, blank=True, verbose_name="Net Income Continuing")
    net_income_discontinued = models.FloatField(null=True, blank=True, verbose_name="Net Income Discontinued")
    income_allocated_to_minority_interest = models.FloatField(null=True, blank=True, verbose_name="Income Minority Interest")
    other_income_statement_items = models.FloatField(null=True, blank=True, verbose_name="Other Income Statement items")
    net_income = models.FloatField(null=True, blank=True, verbose_name="Net Income")
    preferred_dividends = models.FloatField(null=True, blank=True, verbose_name="Preferred Dividends")
    net_income_available_to_shareholders = models.FloatField(null=True, blank=True, verbose_name="Net Income Available to Shareholders")
    eps_basic = models.FloatField(null=True, blank=True, verbose_name="EPS (Basic)")
    eps_diluted = models.FloatField(null=True, blank=True, verbose_name="EPS (diluted)")
    shares_basic = models.FloatField(null=True, blank=True, verbose_name="Shares (Basic)")
    shares_diluted = models.FloatField(null=True, blank=True, verbose_name="Shares (Diluted)")
    shares_eop = models.FloatField(null=True, blank=True, verbose_name="Shares (EOP)")
    shares_eop_change = models.FloatField(null=True, blank=True, verbose_name="Shares Change EOP")
    premiums_earned = models.FloatField(null=True, blank=True, verbose_name="Premiums Earned")
    net_investment_income = models.FloatField(null=True, blank=True, verbose_name="Net Investment Income")
    fees_and_other_income = models.FloatField(null=True, blank=True, verbose_name="Fees and other Income")
    net_policyholder_claims_expense = models.FloatField(null=True, blank=True, verbose_name="Net Policyholder Claims Expense")
    policy_acquisition_expense = models.FloatField(null=True, blank=True, verbose_name="Policy Acquisition Expense")
    interest_expense_insurance = models.FloatField(null=True, blank=True, verbose_name="Interest Expense Insurance")
    total_interest_income = models.FloatField(null=True, blank=True, verbose_name="Total Interest Income")
    total_interest_expense = models.FloatField(null=True, blank=True, verbose_name="Total Interest Expense")
    net_interest_income = models.FloatField(null=True, blank=True, verbose_name="Net Interest Income")
    total_noninterest_revenue = models.FloatField(null=True, blank=True, verbose_name="Total Non-Interest Revenue")
    credit_losses_provision = models.FloatField(null=True, blank=True, verbose_name="Credit Losses Provisions")
    net_interest_income_after_credit_losses_provision = models.FloatField(null=True, blank=True, verbose_name="Net Interest Income after Credit Losses Provisions")
    total_noninterest_expense = models.FloatField(null=True, blank=True, verbose_name="Total Non-Interest Expense")
    da_income_statement_supplemental = models.FloatField(null=True, blank=True, verbose_name="DA Income Statement Supplemental")

    #describe which model should be used when creating a stock filter query with a given quantity. Manly useful for KeyRatios quantities because there it can make a difference if we take yearly or quarterly quantities. For example operating_margin is a quantity based on income statement quantities --> makes more sense to take yearly number as it gets smoother results than quarterly. A quantity like net_debt makes more sense to take from quartely KeyRatios table as it only includes balance sheet quantities and therefore will be more up-to-date. 
    column_metadata = {
        'revenue' : 'income',
        'cogs' : 'income',
        'gross_profit' : 'income',
        'sga' : 'income',
        'rnd' : 'income',
        'special_charges' : 'income',
        'other_opex' : 'income',
        'total_opex' : 'income',
        'operating_income' : 'income',
        'interest_income' : 'income',
        'interest_expense' : 'income',
        'net_interest_income_normal' : 'income',
        'other_nonoperating_income' : 'income',
        'pretax_income' : 'income',
        'income_tax' : 'income',
        'net_income_continuing' : 'income',
        'net_income_discontinued' : 'income',
        'income_allocated_to_minority_interest' : 'income',
        'other_income_statement_items' : 'income',
        'net_income' : 'income',
        'preferred_dividends' : 'income',
        'net_income_available_to_shareholders' : 'income',
        'eps_basic' : 'income',
        'eps_diluted' : 'income',
        'shares_basic' : 'income',
        'shares_diluted' : 'income',
        'shares_eop' : 'income',
        'shares_eop_change' : 'income',
        'premiums_earned' : 'income',
        'net_investment_income' : 'income',
        'fees_and_other_income' : 'income',
        'net_policyholder_claims_expense' : 'income',
        'policy_acquisition_expense' : 'income',
        'interest_expense_insurance' : 'income',
        'total_interest_income' : 'income',
        'total_interest_expense' : 'income',
        'net_interest_income' : 'income',
        'total_noninterest_revenue' : 'income',
        'credit_losses_provision' : 'income',
        'net_interest_income_after_credit_losses_provision' : 'income',
        'total_noninterest_expense' : 'income',
        'da_income_statement_supplemental' : 'income',
    }

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')

class IncomeStatementQuarter(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=10, null=True, blank=True)
    revenue = models.FloatField(null=True, blank=True)
    cogs = models.FloatField(null=True, blank=True)
    gross_profit = models.FloatField(null=True, blank=True)
    sga = models.FloatField(null=True, blank=True)
    rnd = models.FloatField(null=True, blank=True)
    special_charges = models.FloatField(null=True, blank=True)
    other_opex = models.FloatField(null=True, blank=True)
    total_opex = models.FloatField(null=True, blank=True)
    operating_income = models.FloatField(null=True, blank=True)
    interest_income = models.FloatField(null=True, blank=True)
    interest_expense = models.FloatField(null=True, blank=True)
    net_interest_income_normal = models.FloatField(null=True, blank=True)
    other_nonoperating_income = models.FloatField(null=True, blank=True)
    pretax_income = models.FloatField(null=True, blank=True)
    income_tax = models.FloatField(null=True, blank=True)
    net_income_continuing = models.FloatField(null=True, blank=True)
    net_income_discontinued = models.FloatField(null=True, blank=True)
    income_allocated_to_minority_interest = models.FloatField(null=True, blank=True)
    other_income_statement_items = models.FloatField(null=True, blank=True)
    net_income = models.FloatField(null=True, blank=True)
    preferred_dividends = models.FloatField(null=True, blank=True)
    net_income_available_to_shareholders = models.FloatField(null=True, blank=True)
    eps_basic = models.FloatField(null=True, blank=True)
    eps_diluted = models.FloatField(null=True, blank=True)
    shares_basic = models.FloatField(null=True, blank=True)
    shares_diluted = models.FloatField(null=True, blank=True)
    shares_eop = models.FloatField(null=True, blank=True)
    shares_eop_change = models.FloatField(null=True, blank=True)
    premiums_earned = models.FloatField(null=True, blank=True)
    net_investment_income = models.FloatField(null=True, blank=True)
    fees_and_other_income = models.FloatField(null=True, blank=True)
    net_policyholder_claims_expense = models.FloatField(null=True, blank=True)
    policy_acquisition_expense = models.FloatField(null=True, blank=True)
    interest_expense_insurance = models.FloatField(null=True, blank=True)
    total_interest_income = models.FloatField(null=True, blank=True)
    total_interest_expense = models.FloatField(null=True, blank=True)
    net_interest_income = models.FloatField(null=True, blank=True)
    total_noninterest_revenue = models.FloatField(null=True, blank=True)
    credit_losses_provision = models.FloatField(null=True, blank=True)
    net_interest_income_after_credit_losses_provision = models.FloatField(null=True, blank=True)
    total_noninterest_expense = models.FloatField(null=True, blank=True)
    da_income_statement_supplemental = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')

#this model only contains the latest/most up-to-date balance sheet. This means for each ticker we only have one entry (the one with max(period_end_date). This model will be used for the screener functionality --> queries run much faster on this smaller table)
class LatestBalanceSheetAnnual(models.Model):
    qfs_symbol = models.OneToOneField(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    cash_and_equiv = models.FloatField(null=True, blank=True)
    st_investments = models.FloatField(null=True, blank=True)
    receivables = models.FloatField(null=True, blank=True)
    inventories = models.FloatField(null=True, blank=True)
    other_current_assets = models.FloatField(null=True, blank=True)
    total_current_assets = models.FloatField(null=True, blank=True)
    equity_and_other_investments = models.FloatField(null=True, blank=True)
    ppe_gross = models.FloatField(null=True, blank=True)
    accumulated_depreciation = models.FloatField(null=True, blank=True)
    ppe_net = models.FloatField(null=True, blank=True)
    intangible_assets = models.FloatField(null=True, blank=True)
    goodwill = models.FloatField(null=True, blank=True)
    other_lt_assets = models.FloatField(null=True, blank=True)
    total_assets = models.FloatField(null=True, blank=True)
    accounts_payable = models.FloatField(null=True, blank=True)
    tax_payable = models.FloatField(null=True, blank=True)
    current_accrued_liabilities = models.FloatField(null=True, blank=True)
    st_debt = models.FloatField(null=True, blank=True)
    current_deferred_revenue = models.FloatField(null=True, blank=True)
    current_deferred_tax_liability = models.FloatField(null=True, blank=True)
    current_capital_leases = models.FloatField(null=True, blank=True)
    other_current_liabilities = models.FloatField(null=True, blank=True)
    total_current_liabilities = models.FloatField(null=True, blank=True)
    lt_debt = models.FloatField(null=True, blank=True)
    noncurrent_capital_leases = models.FloatField(null=True, blank=True)
    pension_liabilities = models.FloatField(null=True, blank=True)
    noncurrent_deferred_revenue = models.FloatField(null=True, blank=True)
    other_lt_liabilities = models.FloatField(null=True, blank=True)
    total_liabilities = models.FloatField(null=True, blank=True)
    common_stock = models.FloatField(null=True, blank=True)
    preferred_stock = models.FloatField(null=True, blank=True)
    retained_earnings = models.FloatField(null=True, blank=True)
    aoci = models.FloatField(null=True, blank=True)
    apic = models.FloatField(null=True, blank=True)
    treasury_stock = models.FloatField(null=True, blank=True)
    other_equity = models.FloatField(null=True, blank=True)
    minority_interest_liability = models.FloatField(null=True, blank=True)
    total_equity = models.FloatField(null=True, blank=True)
    total_liabilities_and_equity = models.FloatField(null=True, blank=True)
    total_investments = models.FloatField(null=True, blank=True)
    deferred_policy_acquisition_cost = models.FloatField(null=True, blank=True)
    unearned_premiums = models.FloatField(null=True, blank=True)
    future_policy_benefits = models.FloatField(null=True, blank=True)
    loans_gross = models.FloatField(null=True, blank=True)
    allowance_for_loan_losses = models.FloatField(null=True, blank=True)
    unearned_income = models.FloatField(null=True, blank=True)
    loans_net = models.FloatField(null=True, blank=True)
    deposits_liability = models.FloatField(null=True, blank=True)
    operating_assets = models.FloatField(null=True, blank=True) #this field is computed with management command
    operating_liabilities = models.FloatField(null=True, blank=True) #this field is computed with management command
    net_operating_assets = models.FloatField(null=True, blank=True) #this field is computed with management command

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')

class BalanceSheetAnnual(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=10, null=True, blank=True, verbose_name="Reporting Currency")
    cash_and_equiv = models.FloatField(null=True, blank=True, verbose_name="Cash and Equivalents")
    st_investments = models.FloatField(null=True, blank=True, verbose_name="Short-Term Investments")
    receivables = models.FloatField(null=True, blank=True, verbose_name="Accounts Receivable")
    inventories = models.FloatField(null=True, blank=True, verbose_name="Inventories")
    other_current_assets = models.FloatField(null=True, blank=True, verbose_name="Other Current Assets")
    total_current_assets = models.FloatField(null=True, blank=True, verbose_name="Total Current Assets")
    equity_and_other_investments = models.FloatField(null=True, blank=True, verbose_name="Equity and Other Investments")
    ppe_gross = models.FloatField(null=True, blank=True, verbose_name="PP&E Gross")
    accumulated_depreciation = models.FloatField(null=True, blank=True, verbose_name="Accumulated Depreciation")
    ppe_net = models.FloatField(null=True, blank=True, verbose_name="PP&E Net")
    intangible_assets = models.FloatField(null=True, blank=True, verbose_name="Intangible Assets")
    goodwill = models.FloatField(null=True, blank=True, verbose_name="Goodwill")
    other_lt_assets = models.FloatField(null=True, blank=True, verbose_name="Other long-term Assets")
    total_assets = models.FloatField(null=True, blank=True, verbose_name="Total Assets")
    accounts_payable = models.FloatField(null=True, blank=True, verbose_name="Accounts Payables")
    tax_payable = models.FloatField(null=True, blank=True, verbose_name="Tax Payabale")
    current_accrued_liabilities = models.FloatField(null=True, blank=True, verbose_name="Current Accrued Liabilities")
    st_debt = models.FloatField(null=True, blank=True, verbose_name="Short-Term Debt")
    current_deferred_revenue = models.FloatField(null=True, blank=True, verbose_name="Current Deferred Revenue")
    current_deferred_tax_liability = models.FloatField(null=True, blank=True, verbose_name="Current Deferred Tax Liability")
    current_capital_leases = models.FloatField(null=True, blank=True, verbose_name="Current Capital Leases")
    other_current_liabilities = models.FloatField(null=True, blank=True, verbose_name="Other Current Liabilities")
    total_current_liabilities = models.FloatField(null=True, blank=True, verbose_name="Total Current Liabilities")
    lt_debt = models.FloatField(null=True, blank=True, verbose_name="Long-Term Debt")
    noncurrent_capital_leases = models.FloatField(null=True, blank=True, verbose_name="Non-Current Capital Leases")
    pension_liabilities = models.FloatField(null=True, blank=True, verbose_name="Pension Liabilities")
    noncurrent_deferred_revenue = models.FloatField(null=True, blank=True, verbose_name="Non-Current Deferred Revenue")
    other_lt_liabilities = models.FloatField(null=True, blank=True, verbose_name="Other long-term Liabilities")
    total_liabilities = models.FloatField(null=True, blank=True, verbose_name="Total Liabilities")
    common_stock = models.FloatField(null=True, blank=True, verbose_name="Common Stock")
    preferred_stock = models.FloatField(null=True, blank=True, verbose_name="Preferred Stock")
    retained_earnings = models.FloatField(null=True, blank=True, verbose_name="Retained Earnings")
    aoci = models.FloatField(null=True, blank=True, verbose_name="Accumulated Other Comprehensive Income (AOCI)")
    apic = models.FloatField(null=True, blank=True, verbose_name="Additional Paid-In Capital (APIC)")
    treasury_stock = models.FloatField(null=True, blank=True, verbose_name="Treasury Stock")
    other_equity = models.FloatField(null=True, blank=True, verbose_name="Other Equity")
    minority_interest_liability = models.FloatField(null=True, blank=True, verbose_name="Minority Interest Liability")
    total_equity = models.FloatField(null=True, blank=True, verbose_name="Total Equity")
    total_liabilities_and_equity = models.FloatField(null=True, blank=True, verbose_name="Total Liabilities and Equity")
    total_investments = models.FloatField(null=True, blank=True, verbose_name="Total Investments")
    deferred_policy_acquisition_cost = models.FloatField(null=True, blank=True, verbose_name="Deferred Policy Acquisition Cost")
    unearned_premiums = models.FloatField(null=True, blank=True, verbose_name="Unearned Premiums")
    future_policy_benefits = models.FloatField(null=True, blank=True, verbose_name="Future Policy Benefits")
    loans_gross = models.FloatField(null=True, blank=True, verbose_name="Loans Gross")
    allowance_for_loan_losses = models.FloatField(null=True, blank=True, verbose_name="Allowance for Loan Losses")
    unearned_income = models.FloatField(null=True, blank=True, verbose_name="Unearned Income")
    loans_net = models.FloatField(null=True, blank=True, verbose_name="Loans Net")
    deposits_liability = models.FloatField(null=True, blank=True, verbose_name="Deposits Liability")
    operating_assets = models.FloatField(null=True, blank=True, verbose_name="Operating Assets") #this field is computed with management command
    operating_liabilities = models.FloatField(null=True, blank=True, verbose_name="Operating Liabilities") #this field is computed with management command
    net_operating_assets = models.FloatField(null=True, blank=True, verbose_name="Net Operating Assets") #this field is computed with management command


    def __init__(self, *args, **kwargs):
        """
        Constructor is used to generate a unique id for each column in this model; this id will be used on the frontend for identification
        """
        super().__init__(*args, **kwargs)
        for field in self._meta.get_fields():
            if isinstance(field, models.Field):
                field.unique_id = generate_unique_id(self.__class__.__name__, field.name)


    #describe which model should be used when creating a stock filter query with a given quantity. Manly useful for KeyRatios quantities because there it can make a difference if we take yearly or quarterly quantities. For example operating_margin is a quantity based on income statement quantities --> makes more sense to take yearly number as it gets smoother results than quarterly. A quantity like net_debt makes more sense to take from quartely KeyRatios table as it only includes balance sheet quantities and therefore will be more up-to-date. 
    column_metadata = {
        'cash_and_equiv' : 'balance',
        'st_investments' : 'balance',
        'receivables' : 'balance',
        'inventories' : 'balance',
        'other_current_assets' : 'balance',
        'total_current_assets' : 'balance',
        'equity_and_other_investments' : 'balance',
        'ppe_gross' : 'balance',
        'accumulated_depreciation' : 'balance',
        'ppe_net' : 'balance',
        'intangible_assets' : 'balance',
        'goodwill' : 'balance',
        'other_lt_assets' : 'balance',
        'total_assets' : 'balance',
        'accounts_payable' : 'balance',
        'tax_payable' : 'balance',
        'current_accrued_liabilities' : 'balance',
        'st_debt' : 'balance',
        'current_deferred_revenue' : 'balance',
        'current_deferred_tax_liability' : 'balance',
        'current_capital_leases' : 'balance',
        'other_current_liabilities' : 'balance',
        'total_current_liabilities' : 'balance',
        'lt_debt' : 'balance',
        'noncurrent_capital_leases' : 'balance',
        'pension_liabilities' : 'balance',
        'noncurrent_deferred_revenue' : 'balance',
        'other_lt_liabilities' : 'balance',
        'total_liabilities' : 'balance',
        'common_stock' : 'balance',
        'preferred_stock' : 'balance',
        'retained_earnings' : 'balance',
        'aoci' : 'balance',
        'apic' : 'balance',
        'treasury_stock' : 'balance',
        'other_equity' : 'balance',
        'minority_interest_liability' : 'balance',
        'total_equity' : 'balance',
        'total_liabilities_and_equity' : 'balance',
        'total_investments' : 'balance',
        'deferred_policy_acquisition_cost' : 'balance',
        'unearned_premiums' : 'balance',
        'future_policy_benefits' : 'balance',
        'loans_gross' : 'balance',
        'allowance_for_loan_losses' : 'balance',
        'unearned_income' : 'balance',
        'loans_net' : 'balance',
        'deposits_liability' : 'balance',
    }

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')
      

#this model only contains the latest/most up-to-date balance sheet. This means for each ticker we only have one entry (the one with max(period_end_date). This model will be used for the screener functionality --> queries run much faster on this smaller table)
class LatestBalanceSheetQuarter(models.Model):
    qfs_symbol = models.OneToOneField(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    cash_and_equiv = models.FloatField(null=True, blank=True, db_index=True)
    st_investments = models.FloatField(null=True, blank=True)
    receivables = models.FloatField(null=True, blank=True)
    inventories = models.FloatField(null=True, blank=True)
    other_current_assets = models.FloatField(null=True, blank=True)
    total_current_assets = models.FloatField(null=True, blank=True)
    equity_and_other_investments = models.FloatField(null=True, blank=True)
    ppe_gross = models.FloatField(null=True, blank=True)
    accumulated_depreciation = models.FloatField(null=True, blank=True)
    ppe_net = models.FloatField(null=True, blank=True)
    intangible_assets = models.FloatField(null=True, blank=True)
    goodwill = models.FloatField(null=True, blank=True)
    other_lt_assets = models.FloatField(null=True, blank=True)
    total_assets = models.FloatField(null=True, blank=True)
    accounts_payable = models.FloatField(null=True, blank=True)
    tax_payable = models.FloatField(null=True, blank=True)
    current_accrued_liabilities = models.FloatField(null=True, blank=True)
    st_debt = models.FloatField(null=True, blank=True)
    current_deferred_revenue = models.FloatField(null=True, blank=True)
    current_deferred_tax_liability = models.FloatField(null=True, blank=True)
    current_capital_leases = models.FloatField(null=True, blank=True)
    other_current_liabilities = models.FloatField(null=True, blank=True)
    total_current_liabilities = models.FloatField(null=True, blank=True)
    lt_debt = models.FloatField(null=True, blank=True)
    noncurrent_capital_leases = models.FloatField(null=True, blank=True)
    pension_liabilities = models.FloatField(null=True, blank=True)
    noncurrent_deferred_revenue = models.FloatField(null=True, blank=True)
    other_lt_liabilities = models.FloatField(null=True, blank=True)
    total_liabilities = models.FloatField(null=True, blank=True)
    common_stock = models.FloatField(null=True, blank=True)
    preferred_stock = models.FloatField(null=True, blank=True)
    retained_earnings = models.FloatField(null=True, blank=True)
    aoci = models.FloatField(null=True, blank=True)
    apic = models.FloatField(null=True, blank=True)
    treasury_stock = models.FloatField(null=True, blank=True)
    other_equity = models.FloatField(null=True, blank=True)
    minority_interest_liability = models.FloatField(null=True, blank=True)
    total_equity = models.FloatField(null=True, blank=True)
    total_liabilities_and_equity = models.FloatField(null=True, blank=True)
    total_investments = models.FloatField(null=True, blank=True)
    deferred_policy_acquisition_cost = models.FloatField(null=True, blank=True)
    unearned_premiums = models.FloatField(null=True, blank=True)
    future_policy_benefits = models.FloatField(null=True, blank=True)
    loans_gross = models.FloatField(null=True, blank=True)
    allowance_for_loan_losses = models.FloatField(null=True, blank=True)
    unearned_income = models.FloatField(null=True, blank=True)
    loans_net = models.FloatField(null=True, blank=True)
    deposits_liability = models.FloatField(null=True, blank=True)
    operating_assets = models.FloatField(null=True, blank=True) #this field is computed with management command
    operating_liabilities = models.FloatField(null=True, blank=True) #this field is computed with management command
    net_operating_assets = models.FloatField(null=True, blank=True) #this field is computed with management command

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')

class BalanceSheetQuarter(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=10, null=True, blank=True)
    cash_and_equiv = models.FloatField(null=True, blank=True, db_index=True)
    st_investments = models.FloatField(null=True, blank=True)
    receivables = models.FloatField(null=True, blank=True)
    inventories = models.FloatField(null=True, blank=True)
    other_current_assets = models.FloatField(null=True, blank=True)
    total_current_assets = models.FloatField(null=True, blank=True)
    equity_and_other_investments = models.FloatField(null=True, blank=True)
    ppe_gross = models.FloatField(null=True, blank=True)
    accumulated_depreciation = models.FloatField(null=True, blank=True)
    ppe_net = models.FloatField(null=True, blank=True)
    intangible_assets = models.FloatField(null=True, blank=True)
    goodwill = models.FloatField(null=True, blank=True)
    other_lt_assets = models.FloatField(null=True, blank=True)
    total_assets = models.FloatField(null=True, blank=True)
    accounts_payable = models.FloatField(null=True, blank=True)
    tax_payable = models.FloatField(null=True, blank=True)
    current_accrued_liabilities = models.FloatField(null=True, blank=True)
    st_debt = models.FloatField(null=True, blank=True)
    current_deferred_revenue = models.FloatField(null=True, blank=True)
    current_deferred_tax_liability = models.FloatField(null=True, blank=True)
    current_capital_leases = models.FloatField(null=True, blank=True)
    other_current_liabilities = models.FloatField(null=True, blank=True)
    total_current_liabilities = models.FloatField(null=True, blank=True)
    lt_debt = models.FloatField(null=True, blank=True)
    noncurrent_capital_leases = models.FloatField(null=True, blank=True)
    pension_liabilities = models.FloatField(null=True, blank=True)
    noncurrent_deferred_revenue = models.FloatField(null=True, blank=True)
    other_lt_liabilities = models.FloatField(null=True, blank=True)
    total_liabilities = models.FloatField(null=True, blank=True)
    common_stock = models.FloatField(null=True, blank=True)
    preferred_stock = models.FloatField(null=True, blank=True)
    retained_earnings = models.FloatField(null=True, blank=True)
    aoci = models.FloatField(null=True, blank=True)
    apic = models.FloatField(null=True, blank=True)
    treasury_stock = models.FloatField(null=True, blank=True)
    other_equity = models.FloatField(null=True, blank=True)
    minority_interest_liability = models.FloatField(null=True, blank=True)
    total_equity = models.FloatField(null=True, blank=True)
    total_liabilities_and_equity = models.FloatField(null=True, blank=True)
    total_investments = models.FloatField(null=True, blank=True)
    deferred_policy_acquisition_cost = models.FloatField(null=True, blank=True)
    unearned_premiums = models.FloatField(null=True, blank=True)
    future_policy_benefits = models.FloatField(null=True, blank=True)
    loans_gross = models.FloatField(null=True, blank=True)
    allowance_for_loan_losses = models.FloatField(null=True, blank=True)
    unearned_income = models.FloatField(null=True, blank=True)
    loans_net = models.FloatField(null=True, blank=True)
    deposits_liability = models.FloatField(null=True, blank=True)
    operating_assets = models.FloatField(null=True, blank=True, verbose_name="Operating Assets") #this field is computed with management command
    operating_liabilities = models.FloatField(null=True, blank=True, verbose_name="Operating Liabilities") #this field is computed with management command
    net_operating_assets = models.FloatField(null=True, blank=True, verbose_name="Net Operating Assets") #this field is computed with management command

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')

#this model only contains the latest/most up-to-date cash flow statement. This means for each ticker we only have one entry (the one with max(period_end_date). This model will be used for the screener functionality --> queries run much faster on this smaller table)
class LatestCashFlowStatementAnnual(models.Model):
    qfs_symbol = models.OneToOneField(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    cfo_net_income = models.FloatField(null=True, blank=True)
    cfo_da = models.FloatField(null=True, blank=True)
    cfo_receivables = models.FloatField(null=True, blank=True)
    cfo_inventory = models.FloatField(null=True, blank=True)
    cfo_prepaid_expenses = models.FloatField(null=True, blank=True)
    cfo_other_working_capital = models.FloatField(null=True, blank=True)
    cfo_change_in_working_capital = models.FloatField(null=True, blank=True)
    cfo_deferred_tax = models.FloatField(null=True, blank=True)
    cfo_stock_comp = models.FloatField(null=True, blank=True)
    cfo_other_noncash_items = models.FloatField(null=True, blank=True)
    cf_cfo = models.FloatField(null=True, blank=True)
    cfi_ppe_purchases = models.FloatField(null=True, blank=True)
    cfi_ppe_sales = models.FloatField(null=True, blank=True)
    cfi_ppe_net = models.FloatField(null=True, blank=True)
    cfi_acquisitions = models.FloatField(null=True, blank=True)
    cfi_divestitures = models.FloatField(null=True, blank=True)
    cfi_acquisitions_net = models.FloatField(null=True, blank=True)
    cfi_investment_purchases = models.FloatField(null=True, blank=True)
    cfi_investment_sales = models.FloatField(null=True, blank=True)
    cfi_investment_net = models.FloatField(null=True, blank=True)
    cfi_intangibles_net = models.FloatField(null=True, blank=True)
    cfi_other = models.FloatField(null=True, blank=True)
    cf_cfi = models.FloatField(null=True, blank=True)
    cff_common_stock_issued = models.FloatField(null=True, blank=True)
    cff_common_stock_repurchased = models.FloatField(null=True, blank=True)
    cff_common_stock_net = models.FloatField(null=True, blank=True)
    cff_pfd_issued = models.FloatField(null=True, blank=True)
    cff_pfd_repurchased = models.FloatField(null=True, blank=True)
    cff_pfd_net = models.FloatField(null=True, blank=True)
    cff_debt_issued = models.FloatField(null=True, blank=True)
    cff_debt_repaid = models.FloatField(null=True, blank=True)
    cff_debt_net = models.FloatField(null=True, blank=True)
    cff_dividend_paid = models.FloatField(null=True, blank=True)
    cff_other = models.FloatField(null=True, blank=True)
    cf_cff = models.FloatField(null=True, blank=True)
    cf_forex = models.FloatField(null=True, blank=True)
    cf_net_change_in_cash = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')   

class CashFlowStatementAnnual(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=10, null=True, blank=True, verbose_name="Reporting Currency")
    cfo_net_income = models.FloatField(null=True, blank=True, verbose_name="Net Income (CFO)")
    cfo_da = models.FloatField(null=True, blank=True, verbose_name="Depreciation and Amortization (CFO)")
    cfo_receivables = models.FloatField(null=True, blank=True, verbose_name="Accounts Receivables (CFO)")
    cfo_inventory = models.FloatField(null=True, blank=True, verbose_name="Inventory (CFO)")
    cfo_prepaid_expenses = models.FloatField(null=True, blank=True, verbose_name="Prepaid Expenses (CFO)")
    cfo_other_working_capital = models.FloatField(null=True, blank=True, verbose_name="Other Working Capital (CFO)")
    cfo_change_in_working_capital = models.FloatField(null=True, blank=True, verbose_name="Change in Working Capital (CFO)")
    cfo_deferred_tax = models.FloatField(null=True, blank=True, verbose_name="Deferred Tax (CFO)")
    cfo_stock_comp = models.FloatField(null=True, blank=True, verbose_name="Stock Compensation (CFO)")
    cfo_other_noncash_items = models.FloatField(null=True, blank=True, verbose_name="Other Non-Cash items (CFO)")
    cf_cfo = models.FloatField(null=True, blank=True, verbose_name="Cash from Operations")
    cfi_ppe_purchases = models.FloatField(null=True, blank=True, verbose_name="PP&E Purchases (CFI)")
    cfi_ppe_sales = models.FloatField(null=True, blank=True, verbose_name="PP&E Sales (CFI)")
    cfi_ppe_net = models.FloatField(null=True, blank=True, verbose_name="PP&E Net (CFI)")
    cfi_acquisitions = models.FloatField(null=True, blank=True, verbose_name="Acquisitions (CFI)")
    cfi_divestitures = models.FloatField(null=True, blank=True, verbose_name="Divestitures (CFI)")
    cfi_acquisitions_net = models.FloatField(null=True, blank=True, verbose_name="Acquisitions Net (CFI)")
    cfi_investment_purchases = models.FloatField(null=True, blank=True, verbose_name="Investment Purchases (CFI)")
    cfi_investment_sales = models.FloatField(null=True, blank=True, verbose_name="Investment Sales (CFI)")
    cfi_investment_net = models.FloatField(null=True, blank=True, verbose_name="Investments Net (CFI)")
    cfi_intangibles_net = models.FloatField(null=True, blank=True, verbose_name="Intangibles Net (CFI)")
    cfi_other = models.FloatField(null=True, blank=True, verbose_name="Other Investing Cash Flows (CFI)")
    cf_cfi = models.FloatField(null=True, blank=True, verbose_name="Cash from Investing")
    cff_common_stock_issued = models.FloatField(null=True, blank=True, verbose_name="Common Stock Issued (CFF)")
    cff_common_stock_repurchased = models.FloatField(null=True, blank=True, verbose_name="Common Stock Repurchased (CFF)")
    cff_common_stock_net = models.FloatField(null=True, blank=True, verbose_name="Common Stock Net (CFF)")
    cff_pfd_issued = models.FloatField(null=True, blank=True, verbose_name="Preferred Stocks Issued (CFF)")
    cff_pfd_repurchased = models.FloatField(null=True, blank=True, verbose_name="Preferred Stocks Repurchased")
    cff_pfd_net = models.FloatField(null=True, blank=True, verbose_name="Preferred Stocks Net (CFF)")
    cff_debt_issued = models.FloatField(null=True, blank=True, verbose_name="Debt Issued (CFF)")
    cff_debt_repaid = models.FloatField(null=True, blank=True, verbose_name="Debt Repaid (CFF)")
    cff_debt_net = models.FloatField(null=True, blank=True, verbose_name="Debt Net (CFF)")
    cff_dividend_paid = models.FloatField(null=True, blank=True, verbose_name="Dividend Paid (CFF)")
    cff_other = models.FloatField(null=True, blank=True, verbose_name="Other Financing Cash Flows (CFF)")
    cf_cff = models.FloatField(null=True, blank=True, verbose_name="Cash from Financing")
    cf_forex = models.FloatField(null=True, blank=True, verbose_name="Foreign Exchange (CFF)")
    cf_net_change_in_cash = models.FloatField(null=True, blank=True, verbose_name="Net Change in Cash")

    column_metadata = {
        'cfo_net_income' : 'cf',
        'cfo_da' : 'cf',
        'cfo_receivables' : 'cf',
        'cfo_inventory' : 'cf',
        'cfo_prepaid_expenses' : 'cf',
        'cfo_other_working_capital' : 'cf',
        'cfo_change_in_working_capital' : 'cf',
        'cfo_deferred_tax' : 'cf',
        'cfo_stock_comp' : 'cf',
        'cfo_other_noncash_items' : 'cf',
        'cf_cfo' : 'cf',
        'cfi_ppe_purchases' : 'cf',
        'cfi_ppe_sales' : 'cf',
        'cfi_ppe_net' : 'cf',
        'cfi_acquisitions' : 'cf',
        'cfi_divestitures' : 'cf',
        'cfi_acquisitions_net' : 'cf',
        'cfi_investment_purchases' : 'cf',
        'cfi_investment_sales' : 'cf',
        'cfi_investment_net' : 'cf',
        'cfi_intangibles_net' : 'cf',
        'cfi_other' : 'cf',
        'cf_cfi' : 'cf',
        'cff_common_stock_issued' : 'cf',
        'cff_common_stock_repurchased' : 'cf',
        'cff_common_stock_net' : 'cf',
        'cff_pfd_issued' : 'cf',
        'cff_pfd_repurchased' : 'cf',
        'cff_pfd_net' : 'cf',
        'cff_debt_issued' : 'cf',
        'cff_debt_repaid' : 'cf',
        'cff_debt_net' : 'cf',
        'cff_dividend_paid' : 'cf',
        'cff_other' : 'cf',
        'cf_cff' : 'cf',
        'cf_forex' : 'cf',
        'cf_net_change_in_cash' : 'cf',

    }

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')    


class CashFlowStatementQuarter(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    reporting_currency = models.CharField(max_length=10, null=True, blank=True)
    cfo_net_income = models.FloatField(null=True, blank=True)
    cfo_da = models.FloatField(null=True, blank=True)
    cfo_receivables = models.FloatField(null=True, blank=True)
    cfo_inventory = models.FloatField(null=True, blank=True)
    cfo_prepaid_expenses = models.FloatField(null=True, blank=True)
    cfo_other_working_capital = models.FloatField(null=True, blank=True)
    cfo_change_in_working_capital = models.FloatField(null=True, blank=True)
    cfo_deferred_tax = models.FloatField(null=True, blank=True)
    cfo_stock_comp = models.FloatField(null=True, blank=True)
    cfo_other_noncash_items = models.FloatField(null=True, blank=True)
    cf_cfo = models.FloatField(null=True, blank=True)
    cfi_ppe_purchases = models.FloatField(null=True, blank=True)
    cfi_ppe_sales = models.FloatField(null=True, blank=True)
    cfi_ppe_net = models.FloatField(null=True, blank=True)
    cfi_acquisitions = models.FloatField(null=True, blank=True)
    cfi_divestitures = models.FloatField(null=True, blank=True)
    cfi_acquisitions_net = models.FloatField(null=True, blank=True)
    cfi_investment_purchases = models.FloatField(null=True, blank=True)
    cfi_investment_sales = models.FloatField(null=True, blank=True)
    cfi_investment_net = models.FloatField(null=True, blank=True)
    cfi_intangibles_net = models.FloatField(null=True, blank=True)
    cfi_other = models.FloatField(null=True, blank=True)
    cf_cfi = models.FloatField(null=True, blank=True)
    cff_common_stock_issued = models.FloatField(null=True, blank=True)
    cff_common_stock_repurchased = models.FloatField(null=True, blank=True)
    cff_common_stock_net = models.FloatField(null=True, blank=True)
    cff_pfd_issued = models.FloatField(null=True, blank=True)
    cff_pfd_repurchased = models.FloatField(null=True, blank=True)
    cff_pfd_net = models.FloatField(null=True, blank=True)
    cff_debt_issued = models.FloatField(null=True, blank=True)
    cff_debt_repaid = models.FloatField(null=True, blank=True)
    cff_debt_net = models.FloatField(null=True, blank=True)
    cff_dividend_paid = models.FloatField(null=True, blank=True)
    cff_other = models.FloatField(null=True, blank=True)
    cf_cff = models.FloatField(null=True, blank=True)
    cf_forex = models.FloatField(null=True, blank=True)
    cf_net_change_in_cash = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')    

class LatestKeyRatiosAnnual(models.Model):
    qfs_symbol = models.OneToOneField(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    market_cap = models.FloatField(null=True, blank=True, db_index=True)
    period_end_price = models.FloatField(null=True, blank=True)
    enterprise_value = models.FloatField(null=True, blank=True)
    book_value = models.FloatField(null=True, blank=True)
    tangible_book_value = models.FloatField(null=True, blank=True)
    price_to_earnings = models.FloatField(null=True, blank=True)
    price_to_book = models.FloatField(null=True, blank=True)
    price_to_sales = models.FloatField(null=True, blank=True)
    price_to_tangible_book = models.FloatField(null=True, blank=True)
    price_to_fcf = models.FloatField(null=True, blank=True)
    price_to_pretax_income = models.FloatField(null=True, blank=True)
    enterprise_value_to_earnings = models.FloatField(null=True, blank=True)
    enterprise_value_to_book = models.FloatField(null=True, blank=True)
    enterprise_value_to_tangible_book = models.FloatField(null=True, blank=True)
    enterprise_value_to_sales = models.FloatField(null=True, blank=True)
    enterprise_value_to_fcf = models.FloatField(null=True, blank=True)
    enterprise_value_to_pretax_income = models.FloatField(null=True, blank=True)
    ebitda = models.FloatField(null=True, blank=True)
    capex = models.FloatField(null=True, blank=True)
    fcf = models.FloatField(null=True, blank=True)
    earning_assets = models.FloatField(null=True, blank=True)
    policy_revenue = models.FloatField(null=True, blank=True)
    underwriting_profit = models.FloatField(null=True, blank=True)
    dividends = models.FloatField(null=True, blank=True)
    payout_ratio = models.FloatField(null=True, blank=True)
    income_tax_rate = models.FloatField(null=True, blank=True)
    net_debt = models.FloatField(null=True, blank=True)
    gross_margin = models.FloatField(null=True, blank=True)
    ebitda_margin = models.FloatField(null=True, blank=True)
    operating_margin = models.FloatField(null=True, blank=True)
    pretax_margin = models.FloatField(null=True, blank=True)
    net_income_margin = models.FloatField(null=True, blank=True)
    fcf_margin = models.FloatField(null=True, blank=True)
    net_interest_margin = models.FloatField(null=True, blank=True)
    underwriting_margin = models.FloatField(null=True, blank=True)
    roe = models.FloatField(null=True, blank=True)
    roa = models.FloatField(null=True, blank=True)
    roic = models.FloatField(null=True, blank=True)
    roic_legacy = models.FloatField(null=True, blank=True)
    roce = models.FloatField(null=True, blank=True)
    rotce = models.FloatField(null=True, blank=True)
    roi = models.FloatField(null=True, blank=True)
    debt_to_equity = models.FloatField(null=True, blank=True)
    debt_to_assets = models.FloatField(null=True, blank=True)
    equity_to_assets = models.FloatField(null=True, blank=True)
    assets_to_equity = models.FloatField(null=True, blank=True)
    current_ratio = models.FloatField(null=True, blank=True)
    earning_assets_to_equity = models.FloatField(null=True, blank=True)
    loans_to_deposits = models.FloatField(null=True, blank=True)
    loan_loss_reserve_to_loans = models.FloatField(null=True, blank=True)
    revenue_per_share = models.FloatField(null=True, blank=True)
    ebitda_per_share = models.FloatField(null=True, blank=True)
    operating_income_per_share = models.FloatField(null=True, blank=True)
    pretax_income_per_share = models.FloatField(null=True, blank=True)
    fcf_per_share = models.FloatField(null=True, blank=True)
    book_value_per_share = models.FloatField(null=True, blank=True)
    tangible_book_per_share = models.FloatField(null=True, blank=True)
    premiums_per_share = models.FloatField(null=True, blank=True)
    revenue_growth = models.FloatField(null=True, blank=True)
    gross_profit_growth = models.FloatField(null=True, blank=True)
    ebitda_growth = models.FloatField(null=True, blank=True)
    operating_income_growth = models.FloatField(null=True, blank=True)
    pretax_income_growth = models.FloatField(null=True, blank=True)
    net_income_growth = models.FloatField(null=True, blank=True)
    eps_diluted_growth = models.FloatField(null=True, blank=True)
    shares_diluted_growth = models.FloatField(null=True, blank=True)
    shares_eop_growth = models.FloatField(null=True, blank=True)
    cash_and_equiv_growth = models.FloatField(null=True, blank=True)
    ppe_growth = models.FloatField(null=True, blank=True)
    total_assets_growth = models.FloatField(null=True, blank=True)
    total_equity_growth = models.FloatField(null=True, blank=True)
    cfo_growth = models.FloatField(null=True, blank=True)
    capex_growth = models.FloatField(null=True, blank=True)
    fcf_growth = models.FloatField(null=True, blank=True)
    revenue_cagr_10 = models.FloatField(null=True, blank=True)
    eps_diluted_cagr_10 = models.FloatField(null=True, blank=True)
    total_assets_cagr_10 = models.FloatField(null=True, blank=True)
    total_equity_cagr_10 = models.FloatField(null=True, blank=True)
    cf_cfo_cagr_10 = models.FloatField(null=True, blank=True)
    fcf_cagr_10 = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')


class KeyRatiosAnnual(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    market_cap = models.FloatField(null=True, blank=True, db_index=True, verbose_name="Market Capitalization")
    period_end_price = models.FloatField(null=True, blank=True, verbose_name="Period End Price")
    enterprise_value = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value (EV)")
    book_value = models.FloatField(null=True, blank=True, verbose_name="Book Value")
    tangible_book_value = models.FloatField(null=True, blank=True, verbose_name="Tangible Book Value")
    price_to_earnings = models.FloatField(null=True, blank=True, verbose_name="Price-to-Earnings (P/E)")
    price_to_book = models.FloatField(null=True, blank=True, verbose_name="Price-to-Book (P/B)")
    price_to_sales = models.FloatField(null=True, blank=True, verbose_name="Price-to-Sales (P/S)")
    price_to_tangible_book = models.FloatField(null=True, blank=True, verbose_name="Price-to-Tangible-Book-Value (PTBV)")
    price_to_fcf = models.FloatField(null=True, blank=True, verbose_name="Price to Free Cash Flow (P/FCF)")
    price_to_pretax_income = models.FloatField(null=True, blank=True, verbose_name="Price to Pretax Income")
    enterprise_value_to_earnings = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Earnings (EV/E)")
    enterprise_value_to_book = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Book (EV/B)")
    enterprise_value_to_tangible_book = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Tangible Book (EV/TB)")
    enterprise_value_to_sales = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Sales (EV/S)")
    enterprise_value_to_fcf = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Free Cash Flow (EV/FCF)")
    enterprise_value_to_pretax_income = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Pretax Income")
    ebitda = models.FloatField(null=True, blank=True, verbose_name="EBITDA")
    capex = models.FloatField(null=True, blank=True, verbose_name="Capital Expenditures (Capex)")
    fcf = models.FloatField(null=True, blank=True, verbose_name="Free Cash Flow (FCF)")
    earning_assets = models.FloatField(null=True, blank=True, verbose_name="Earnings Assets")
    policy_revenue = models.FloatField(null=True, blank=True, verbose_name="Policy Revenue")
    underwriting_profit = models.FloatField(null=True, blank=True, verbose_name="Underwriting Profit")
    dividends = models.FloatField(null=True, blank=True, verbose_name="Dividends")
    payout_ratio = models.FloatField(null=True, blank=True, verbose_name="Payout Ratio")
    income_tax_rate = models.FloatField(null=True, blank=True, verbose_name="Income Tax Rate")
    net_debt = models.FloatField(null=True, blank=True, verbose_name="Net Debt")
    gross_margin = models.FloatField(null=True, blank=True, verbose_name="Gross Margin")
    ebitda_margin = models.FloatField(null=True, blank=True, verbose_name="EBITDA Margin")
    operating_margin = models.FloatField(null=True, blank=True, verbose_name="Operating Margin")
    pretax_margin = models.FloatField(null=True, blank=True, verbose_name="Pretax Margin")
    net_income_margin = models.FloatField(null=True, blank=True, verbose_name="Net Income Margin")
    fcf_margin = models.FloatField(null=True, blank=True, verbose_name="Free Cash Flow Margin")
    net_interest_margin = models.FloatField(null=True, blank=True, verbose_name="Net Interest Margin")
    underwriting_margin = models.FloatField(null=True, blank=True, verbose_name="Underwriting Margin")
    roe = models.FloatField(null=True, blank=True, verbose_name="Return on Equity (ROE)")
    roa = models.FloatField(null=True, blank=True, verbose_name="Return on Assets (ROA)")
    roic = models.FloatField(null=True, blank=True, verbose_name="Return on Invested Capital (ROIC)")
    roic_legacy = models.FloatField(null=True, blank=True, verbose_name="ROIC legacy")
    roce = models.FloatField(null=True, blank=True, verbose_name="Return on Capital Employed")
    rotce = models.FloatField(null=True, blank=True, verbose_name="Return on Tangible Capital Employed")
    roi = models.FloatField(null=True, blank=True, verbose_name="Return on Investment (ROI)")
    debt_to_equity = models.FloatField(null=True, blank=True, verbose_name="Debt to Equity")
    debt_to_assets = models.FloatField(null=True, blank=True, verbose_name="Debt to Assets")
    equity_to_assets = models.FloatField(null=True, blank=True, verbose_name="Equity to Assets")
    assets_to_equity = models.FloatField(null=True, blank=True, verbose_name="Assets to Equity")
    current_ratio = models.FloatField(null=True, blank=True, verbose_name="Current Ratio")
    earning_assets_to_equity = models.FloatField(null=True, blank=True, verbose_name="Earning Assets to Equity")
    loans_to_deposits = models.FloatField(null=True, blank=True, verbose_name="Loans to Deposits")
    loan_loss_reserve_to_loans = models.FloatField(null=True, blank=True, verbose_name="Loan Loss Reserve to Loans")
    revenue_per_share = models.FloatField(null=True, blank=True, verbose_name="Revenue per Share")
    ebitda_per_share = models.FloatField(null=True, blank=True, verbose_name="EBITDA per Share")
    operating_income_per_share = models.FloatField(null=True, blank=True, verbose_name="Operating Income per Share")
    pretax_income_per_share = models.FloatField(null=True, blank=True, verbose_name="Pretax Income per Share")
    fcf_per_share = models.FloatField(null=True, blank=True, verbose_name="FCF per Share")
    book_value_per_share = models.FloatField(null=True, blank=True, verbose_name="Book Value per Share")
    tangible_book_per_share = models.FloatField(null=True, blank=True, verbose_name="Tangible Book per Share")
    premiums_per_share = models.FloatField(null=True, blank=True, verbose_name="Premiums per Share")
    revenue_growth = models.FloatField(null=True, blank=True, verbose_name="Revenue Growth")
    gross_profit_growth = models.FloatField(null=True, blank=True, verbose_name="Gross Profit Growth")
    ebitda_growth = models.FloatField(null=True, blank=True, verbose_name="EBITDA Growth")
    operating_income_growth = models.FloatField(null=True, blank=True, verbose_name="Operating Income Growth")
    pretax_income_growth = models.FloatField(null=True, blank=True, verbose_name="Pretax Income Growth")
    net_income_growth = models.FloatField(null=True, blank=True, verbose_name="Net Income Growth")
    eps_diluted_growth = models.FloatField(null=True, blank=True, verbose_name="EPS diluted Growth")
    shares_diluted_growth = models.FloatField(null=True, blank=True, verbose_name="Shares Diluted Growth")
    shares_eop_growth = models.FloatField(null=True, blank=True, verbose_name="Shares EOP Growth")
    cash_and_equiv_growth = models.FloatField(null=True, blank=True, verbose_name="Cash and Equivalents Growth")
    ppe_growth = models.FloatField(null=True, blank=True, verbose_name="PP&E Growth")
    total_assets_growth = models.FloatField(null=True, blank=True, verbose_name="Total Assets Growth")
    total_equity_growth = models.FloatField(null=True, blank=True, verbose_name="Total Equity Growth")
    cfo_growth = models.FloatField(null=True, blank=True, verbose_name="Operating Cash Flow Growth")
    capex_growth = models.FloatField(null=True, blank=True, verbose_name="Capex Growth")
    fcf_growth = models.FloatField(null=True, blank=True, verbose_name="Free Cash Flow Growth")
    revenue_cagr_10 = models.FloatField(null=True, blank=True, verbose_name="Revenue CAGR 10Y")
    eps_diluted_cagr_10 = models.FloatField(null=True, blank=True, verbose_name="EPS diluted CAGR 10Y")
    total_assets_cagr_10 = models.FloatField(null=True, blank=True, verbose_name="Total Assets CAGR 10Y")
    total_equity_cagr_10 = models.FloatField(null=True, blank=True, verbose_name="Total Equity CAGR 10Y")
    cf_cfo_cagr_10 = models.FloatField(null=True, blank=True, verbose_name="CFO CAGR 10Y")
    fcf_cagr_10 = models.FloatField(null=True, blank=True, verbose_name="FCF CAGR 10Y")
    rnoa = models.FloatField(null=True, blank=True, verbose_name="RNOA")

    column_metadata = {
        'market_cap' : 'kr_q',
        'period_end_price' : 'kr_q',
        'enterprise_value' : 'kr_q',
        'book_value' : 'kr_q',
        'tangible_book_value' : 'kr_q',
        'price_to_earnings' : 'kr_y',
        'price_to_book' : 'kr_q',
        'price_to_sales' : 'kr_y',
        'price_to_tangible_book' : 'kr_q',
        'price_to_fcf' : 'kr_y',
        'price_to_pretax_income' : 'kr_y',
        'enterprise_value_to_earnings' : 'kr_y',
        'enterprise_value_to_book' : 'kr_q',
        'enterprise_value_to_tangible_book' : 'kr_q',
        'enterprise_value_to_sales' : 'kr_y',
        'enterprise_value_to_fcf' : 'kr_y',
        'enterprise_value_to_pretax_income' : 'kr_y',
        'ebitda' : 'kr_y',
        'capex' : 'kr_y',
        'fcf' : 'kr_y',
        'earning_assets' : 'kr_y',
        'policy_revenue' : 'kr_y',
        'underwriting_profit' : 'kr_y',
        'dividends' : 'kr_y',
        'payout_ratio' : 'kr_y',
        'income_tax_rate' : 'kr_y',
        'net_debt' : 'kr_q',
        'gross_margin' : 'kr_y',
        'ebitda_margin' : 'kr_y',
        'operating_margin' : 'kr_y',
        'pretax_margin' : 'kr_y',
        'net_income_margin' : 'kr_y',
        'fcf_margin' : 'kr_y',
        'net_interest_margin' : 'kr_y',
        'underwriting_margin' : 'kr_y',
        'roe' : 'kr_y',
        'roa' : 'kr_y',
        'roic' : 'kr_y',
        'roce' : 'kr_y',
        'rotce' : 'kr_y',
        'roi' : 'kr_y',
        'debt_to_equity' : 'kr_q',
        'debt_to_assets' : 'kr_q',
        'equity_to_assets' : 'kr_q',
        'assets_to_equity' : 'kr_q',
        'current_ratio' : 'kr_q',
        'earning_assets_to_equity' : 'kr_y',
        'loans_to_deposits' : 'kr_q',
        'loan_loss_reserve_to_loans' : 'kr_q',
        'revenue_per_share' : 'kr_y',
        'ebitda_per_share' : 'kr_y',
        'operating_income_per_share' : 'kr_y',
        'pretax_income_per_share' : 'kr_y',
        'fcf_per_share' : 'kr_y',
        'book_value_per_share' : 'kr_q',
        'tangible_book_per_share' : 'kr_q',
        'premiums_per_share' : 'kr_q',
        'revenue_growth' : 'kr_y',
        'gross_profit_growth' : 'kr_y',
        'ebitda_growth' : 'kr_y',
        'operating_income_growth' : 'kr_y',
        'pretax_income_growth' : 'kr_y',
        'net_income_growth' : 'kr_y',
        'eps_diluted_growth' : 'kr_y',
        'shares_diluted_growth' : 'kr_y',
        'shares_eop_growth' : 'kr_y',
        'cash_and_equiv_growth' : 'kr_y',
        'ppe_growth' : 'kr_y',
        'total_assets_growth' : 'kr_y',
        'total_equity_growth' : 'kr_y',
        'cfo_growth' : 'kr_y',
        'capex_growth' : 'kr_y',
        'fcf_growth' : 'kr_y',
        'revenue_cagr_10' : 'kr_y',
        'eps_diluted_cagr_10' : 'kr_y',
        'total_assets_cagr_10' : 'kr_y',
        'total_equity_cagr_10' : 'kr_y',
        'cf_cfo_cagr_10' : 'kr_y',
        'fcf_cagr_10' : 'kr_y',

    }

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')

class LatestKeyRatiosQuarter(models.Model):
    qfs_symbol = models.OneToOneField(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    market_cap = models.FloatField(null=True, blank=True, db_index=True)
    period_end_price = models.FloatField(null=True, blank=True)
    enterprise_value = models.FloatField(null=True, blank=True)
    book_value = models.FloatField(null=True, blank=True)
    tangible_book_value = models.FloatField(null=True, blank=True)
    price_to_earnings = models.FloatField(null=True, blank=True)
    price_to_book = models.FloatField(null=True, blank=True)
    price_to_sales = models.FloatField(null=True, blank=True)
    price_to_tangible_book = models.FloatField(null=True, blank=True)
    price_to_fcf = models.FloatField(null=True, blank=True)
    price_to_pretax_income = models.FloatField(null=True, blank=True)
    enterprise_value_to_earnings = models.FloatField(null=True, blank=True)
    enterprise_value_to_book = models.FloatField(null=True, blank=True)
    enterprise_value_to_tangible_book = models.FloatField(null=True, blank=True)
    enterprise_value_to_sales = models.FloatField(null=True, blank=True)
    enterprise_value_to_fcf = models.FloatField(null=True, blank=True)
    enterprise_value_to_pretax_income = models.FloatField(null=True, blank=True)
    ebitda = models.FloatField(null=True, blank=True)
    capex = models.FloatField(null=True, blank=True)
    fcf = models.FloatField(null=True, blank=True)
    earning_assets = models.FloatField(null=True, blank=True)
    policy_revenue = models.FloatField(null=True, blank=True)
    underwriting_profit = models.FloatField(null=True, blank=True)
    dividends = models.FloatField(null=True, blank=True)
    payout_ratio = models.FloatField(null=True, blank=True)
    income_tax_rate = models.FloatField(null=True, blank=True)
    net_debt = models.FloatField(null=True, blank=True)
    gross_margin = models.FloatField(null=True, blank=True)
    ebitda_margin = models.FloatField(null=True, blank=True)
    operating_margin = models.FloatField(null=True, blank=True)
    pretax_margin = models.FloatField(null=True, blank=True)
    net_income_margin = models.FloatField(null=True, blank=True)
    fcf_margin = models.FloatField(null=True, blank=True)
    net_interest_margin = models.FloatField(null=True, blank=True)
    underwriting_margin = models.FloatField(null=True, blank=True)
    roe = models.FloatField(null=True, blank=True)
    roa = models.FloatField(null=True, blank=True)
    roic = models.FloatField(null=True, blank=True)
    roic_legacy = models.FloatField(null=True, blank=True)
    roce = models.FloatField(null=True, blank=True)
    rotce = models.FloatField(null=True, blank=True)
    roi = models.FloatField(null=True, blank=True)
    debt_to_equity = models.FloatField(null=True, blank=True)
    equity_to_assets = models.FloatField(null=True, blank=True)
    debt_to_assets = models.FloatField(null=True, blank=True)
    assets_to_equity = models.FloatField(null=True, blank=True)
    current_ratio = models.FloatField(null=True, blank=True)
    earning_assets_to_equity = models.FloatField(null=True, blank=True)
    loans_to_deposits = models.FloatField(null=True, blank=True)
    loan_loss_reserve_to_loans = models.FloatField(null=True, blank=True)
    revenue_per_share = models.FloatField(null=True, blank=True)
    ebitda_per_share = models.FloatField(null=True, blank=True)
    operating_income_per_share = models.FloatField(null=True, blank=True)
    pretax_income_per_share = models.FloatField(null=True, blank=True)
    fcf_per_share = models.FloatField(null=True, blank=True)
    book_value_per_share = models.FloatField(null=True, blank=True)
    tangible_book_per_share = models.FloatField(null=True, blank=True)
    premiums_per_share = models.FloatField(null=True, blank=True)
    revenue_growth = models.FloatField(null=True, blank=True)
    gross_profit_growth = models.FloatField(null=True, blank=True)
    ebitda_growth = models.FloatField(null=True, blank=True)
    operating_income_growth = models.FloatField(null=True, blank=True)
    pretax_income_growth = models.FloatField(null=True, blank=True)
    net_income_growth = models.FloatField(null=True, blank=True)
    eps_diluted_growth = models.FloatField(null=True, blank=True)
    shares_diluted_growth = models.FloatField(null=True, blank=True)
    shares_eop_growth = models.FloatField(null=True, blank=True)
    cash_and_equiv_growth = models.FloatField(null=True, blank=True)
    ppe_growth = models.FloatField(null=True, blank=True)
    total_assets_growth = models.FloatField(null=True, blank=True)
    total_equity_growth = models.FloatField(null=True, blank=True)
    cfo_growth = models.FloatField(null=True, blank=True)
    capex_growth = models.FloatField(null=True, blank=True)
    fcf_growth = models.FloatField(null=True, blank=True)
    revenue_cagr_10 = models.FloatField(null=True, blank=True)
    eps_diluted_cagr_10 = models.FloatField(null=True, blank=True)
    total_assets_cagr_10 = models.FloatField(null=True, blank=True)
    total_equity_cagr_10 = models.FloatField(null=True, blank=True)
    cf_cfo_cagr_10 = models.FloatField(null=True, blank=True)
    fcf_cagr_10 = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')


class KeyRatiosQuarter(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)
    period_end_date = models.DateField(db_index=True)
    market_cap = models.FloatField(null=True, blank=True, db_index=True)
    period_end_price = models.FloatField(null=True, blank=True)
    enterprise_value = models.FloatField(null=True, blank=True)
    book_value = models.FloatField(null=True, blank=True)
    tangible_book_value = models.FloatField(null=True, blank=True)
    price_to_earnings = models.FloatField(null=True, blank=True)
    price_to_book = models.FloatField(null=True, blank=True)
    price_to_sales = models.FloatField(null=True, blank=True)
    price_to_tangible_book = models.FloatField(null=True, blank=True)
    price_to_fcf = models.FloatField(null=True, blank=True)
    price_to_pretax_income = models.FloatField(null=True, blank=True)
    enterprise_value_to_earnings = models.FloatField(null=True, blank=True)
    enterprise_value_to_book = models.FloatField(null=True, blank=True)
    enterprise_value_to_tangible_book = models.FloatField(null=True, blank=True)
    enterprise_value_to_sales = models.FloatField(null=True, blank=True)
    enterprise_value_to_fcf = models.FloatField(null=True, blank=True)
    enterprise_value_to_pretax_income = models.FloatField(null=True, blank=True)
    ebitda = models.FloatField(null=True, blank=True)
    capex = models.FloatField(null=True, blank=True)
    fcf = models.FloatField(null=True, blank=True)
    earning_assets = models.FloatField(null=True, blank=True)
    policy_revenue = models.FloatField(null=True, blank=True)
    underwriting_profit = models.FloatField(null=True, blank=True)
    dividends = models.FloatField(null=True, blank=True)
    payout_ratio = models.FloatField(null=True, blank=True)
    income_tax_rate = models.FloatField(null=True, blank=True)
    net_debt = models.FloatField(null=True, blank=True)
    gross_margin = models.FloatField(null=True, blank=True)
    ebitda_margin = models.FloatField(null=True, blank=True)
    operating_margin = models.FloatField(null=True, blank=True)
    pretax_margin = models.FloatField(null=True, blank=True)
    net_income_margin = models.FloatField(null=True, blank=True)
    fcf_margin = models.FloatField(null=True, blank=True)
    net_interest_margin = models.FloatField(null=True, blank=True)
    underwriting_margin = models.FloatField(null=True, blank=True)
    roe = models.FloatField(null=True, blank=True)
    roa = models.FloatField(null=True, blank=True)
    roic = models.FloatField(null=True, blank=True)
    roic_legacy = models.FloatField(null=True, blank=True)
    roce = models.FloatField(null=True, blank=True)
    rotce = models.FloatField(null=True, blank=True)
    roi = models.FloatField(null=True, blank=True)
    debt_to_equity = models.FloatField(null=True, blank=True)
    equity_to_assets = models.FloatField(null=True, blank=True)
    debt_to_assets = models.FloatField(null=True, blank=True)
    assets_to_equity = models.FloatField(null=True, blank=True)
    current_ratio = models.FloatField(null=True, blank=True)
    earning_assets_to_equity = models.FloatField(null=True, blank=True)
    loans_to_deposits = models.FloatField(null=True, blank=True)
    loan_loss_reserve_to_loans = models.FloatField(null=True, blank=True)
    revenue_per_share = models.FloatField(null=True, blank=True)
    ebitda_per_share = models.FloatField(null=True, blank=True)
    operating_income_per_share = models.FloatField(null=True, blank=True)
    pretax_income_per_share = models.FloatField(null=True, blank=True)
    fcf_per_share = models.FloatField(null=True, blank=True)
    book_value_per_share = models.FloatField(null=True, blank=True)
    tangible_book_per_share = models.FloatField(null=True, blank=True)
    premiums_per_share = models.FloatField(null=True, blank=True)
    revenue_growth = models.FloatField(null=True, blank=True)
    gross_profit_growth = models.FloatField(null=True, blank=True)
    ebitda_growth = models.FloatField(null=True, blank=True)
    operating_income_growth = models.FloatField(null=True, blank=True)
    pretax_income_growth = models.FloatField(null=True, blank=True)
    net_income_growth = models.FloatField(null=True, blank=True)
    eps_diluted_growth = models.FloatField(null=True, blank=True)
    shares_diluted_growth = models.FloatField(null=True, blank=True)
    shares_eop_growth = models.FloatField(null=True, blank=True)
    cash_and_equiv_growth = models.FloatField(null=True, blank=True)
    ppe_growth = models.FloatField(null=True, blank=True)
    total_assets_growth = models.FloatField(null=True, blank=True)
    total_equity_growth = models.FloatField(null=True, blank=True)
    cfo_growth = models.FloatField(null=True, blank=True)
    capex_growth = models.FloatField(null=True, blank=True)
    fcf_growth = models.FloatField(null=True, blank=True)
    revenue_cagr_10 = models.FloatField(null=True, blank=True)
    eps_diluted_cagr_10 = models.FloatField(null=True, blank=True)
    total_assets_cagr_10 = models.FloatField(null=True, blank=True)
    total_equity_cagr_10 = models.FloatField(null=True, blank=True)
    cf_cfo_cagr_10 = models.FloatField(null=True, blank=True)
    fcf_cagr_10 = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('qfs_symbol', 'period_end_date')




#this model combines all fields from the other models. So we have a single table that we can query for the screen functionality
#
#Populated by migrations/quickfs_database/migrate_screener_data.py from TradedCompanies, Valuation,
#IncomeStatementAnnual, BalanceSheetAnnual/Quarter, and CashFlowStatementAnnual. The market_cap_y/
#price_to_book_y/roe_y/etc. columns are sourced from KeyRatiosAnnual/KeyRatiosQuarter, which date back
#to the old QuickFS data provider and are no longer refreshed (EODHD, the current provider, doesn't
#supply equivalent pre-computed ratios) - treat those columns as frozen/legacy until removed.
#
#Currency guarantee: every other numeric column on a given row is expressed in that company's trading
#currency (= TradedCompanies.currency, the `currency` field below), never its raw filing currency.
#For a company like YRD.US (files in CNY, trades in USD), revenue_y/cogs_y/net_income_y/etc. are all
#already converted to USD before being written here - the FX conversion happens once, upstream in
#migrate_screener_data.py, never on read. See FxRate for the conversion rates used.
class ScreenerData(models.Model):
    qfs_symbol = models.ForeignKey(TradedCompanies, to_field='qfs_symbol', on_delete=models.CASCADE, db_index=True)

    #IMPORTANT: Whenever you add new fields you also need to add them to the metadata attribute at the bottom

    #currency all numeric columns on this row are expressed in (= TradedCompanies.currency, the trading currency)
    currency = models.CharField(max_length=10, null=True, blank=True, verbose_name="Currency")

    #TradedCompany fields
    ticker = models.CharField(max_length=30, null=True, blank=True)
    exchange = models.CharField(max_length=30, verbose_name="Exchange", null=True, blank=True)
    name = models.CharField(max_length=500, verbose_name="Name", null=True, blank=True)
    industry = models.CharField(max_length=300, null=True, blank=True, verbose_name="Industry")
    last_close_price = models.FloatField(verbose_name="Last close price", null=True, blank=True)

    # Valuation
    epv_business = models.FloatField(null=True, blank=True)
    epv_per_share = models.FloatField(null=True, blank=True)
    epv_business_ttm = models.FloatField(null=True, blank=True)
    epv_per_share_ttm = models.FloatField(null=True, blank=True)
    penman_equity = models.FloatField(null=True, blank=True)
    penman_per_share = models.FloatField(null=True, blank=True)
    penman_g = models.FloatField(null=True, blank=True)  # Implied growth rate
    rnoa = models.FloatField(null=True, blank=True)
    penman_equity_ttm = models.FloatField(null=True, blank=True)
    penman_per_share_ttm = models.FloatField(null=True, blank=True)
    penman_g_ttm = models.FloatField(null=True, blank=True)  # Implied growth rate
    rnoa_ttm = models.FloatField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)

    # Income Statement (Annual)
    revenue_y = models.FloatField(null=True, blank=True)
    cogs_y = models.FloatField(null=True, blank=True)
    gross_profit_y = models.FloatField(null=True, blank=True)
    sga_y = models.FloatField(null=True, blank=True)
    rnd_y = models.FloatField(null=True, blank=True)
    special_charges_y = models.FloatField(null=True, blank=True)
    other_opex_y = models.FloatField(null=True, blank=True)
    total_opex_y = models.FloatField(null=True, blank=True)
    operating_income_y = models.FloatField(null=True, blank=True)
    interest_income_y = models.FloatField(null=True, blank=True)
    interest_expense_y = models.FloatField(null=True, blank=True)
    net_interest_income_normal_y = models.FloatField(null=True, blank=True)
    other_nonoperating_income_y = models.FloatField(null=True, blank=True)
    pretax_income_y = models.FloatField(null=True, blank=True)
    income_tax_y = models.FloatField(null=True, blank=True)
    net_income_continuing_y = models.FloatField(null=True, blank=True)
    net_income_discontinued_y = models.FloatField(null=True, blank=True)
    income_allocated_to_minority_interest_y = models.FloatField(null=True, blank=True)
    other_income_statement_items_y = models.FloatField(null=True, blank=True)
    net_income_y = models.FloatField(null=True, blank=True)
    preferred_dividends_y = models.FloatField(null=True, blank=True)
    net_income_available_to_shareholders_y = models.FloatField(null=True, blank=True)
    eps_basic_y = models.FloatField(null=True, blank=True)
    eps_diluted_y = models.FloatField(null=True, blank=True)
    shares_basic_y = models.FloatField(null=True, blank=True)
    shares_diluted_y = models.FloatField(null=True, blank=True)
    shares_eop_y = models.FloatField(null=True, blank=True)
    shares_eop_change_y = models.FloatField(null=True, blank=True)

    # Balance Sheet (Annual)
    cash_and_equiv_y = models.FloatField(null=True, blank=True)
    st_investments_y = models.FloatField(null=True, blank=True)
    receivables_y = models.FloatField(null=True, blank=True)
    inventories_y = models.FloatField(null=True, blank=True)
    other_current_assets_y = models.FloatField(null=True, blank=True)
    total_current_assets_y = models.FloatField(null=True, blank=True)
    equity_and_other_investments_y = models.FloatField(null=True, blank=True)
    ppe_gross_y = models.FloatField(null=True, blank=True)
    accumulated_depreciation_y = models.FloatField(null=True, blank=True)
    ppe_net_y = models.FloatField(null=True, blank=True)
    intangible_assets_y = models.FloatField(null=True, blank=True)
    goodwill_y = models.FloatField(null=True, blank=True)
    other_lt_assets_y = models.FloatField(null=True, blank=True)
    total_assets_y = models.FloatField(null=True, blank=True)
    accounts_payable_y = models.FloatField(null=True, blank=True)
    tax_payable_y = models.FloatField(null=True, blank=True)
    current_accrued_liabilities_y = models.FloatField(null=True, blank=True)
    st_debt_y = models.FloatField(null=True, blank=True)
    current_deferred_revenue_y = models.FloatField(null=True, blank=True)
    current_deferred_tax_liability_y = models.FloatField(null=True, blank=True)
    current_capital_leases_y = models.FloatField(null=True, blank=True)
    other_current_liabilities_y = models.FloatField(null=True, blank=True)
    total_current_liabilities_y = models.FloatField(null=True, blank=True)
    lt_debt_y = models.FloatField(null=True, blank=True)
    noncurrent_capital_leases_y = models.FloatField(null=True, blank=True)
    pension_liabilities_y = models.FloatField(null=True, blank=True)
    noncurrent_deferred_revenue_y = models.FloatField(null=True, blank=True)
    other_lt_liabilities_y = models.FloatField(null=True, blank=True)
    total_liabilities_y = models.FloatField(null=True, blank=True)
    common_stock_y = models.FloatField(null=True, blank=True)
    preferred_stock_y = models.FloatField(null=True, blank=True)
    retained_earnings_y = models.FloatField(null=True, blank=True)
    aoci_y = models.FloatField(null=True, blank=True)
    apic_y = models.FloatField(null=True, blank=True)
    treasury_stock_y = models.FloatField(null=True, blank=True)
    other_equity_y = models.FloatField(null=True, blank=True)
    minority_interest_liability_y = models.FloatField(null=True, blank=True)
    total_equity_y = models.FloatField(null=True, blank=True)
    total_liabilities_and_equity_y = models.FloatField(null=True, blank=True)

    # Balance Sheet (Quarterly) TO BE ADDED; for first testing purposes we will keep it simple
    cash_and_equiv_q = models.FloatField(null=True, blank=True)
    st_investments_q = models.FloatField(null=True, blank=True)
    receivables_q = models.FloatField(null=True, blank=True)
    inventories_q = models.FloatField(null=True, blank=True)
    other_current_assets_q = models.FloatField(null=True, blank=True)
    total_current_assets_q = models.FloatField(null=True, blank=True)
    equity_and_other_investments_q = models.FloatField(null=True, blank=True)
    ppe_gross_q = models.FloatField(null=True, blank=True)
    accumulated_depreciation_q = models.FloatField(null=True, blank=True)
    ppe_net_q = models.FloatField(null=True, blank=True)
    intangible_assets_q = models.FloatField(null=True, blank=True)
    goodwill_q = models.FloatField(null=True, blank=True)
    other_lt_assets_q = models.FloatField(null=True, blank=True)
    total_assets_q = models.FloatField(null=True, blank=True)
    accounts_payable_q = models.FloatField(null=True, blank=True)
    tax_payable_q = models.FloatField(null=True, blank=True)
    current_accrued_liabilities_q = models.FloatField(null=True, blank=True)
    st_debt_q = models.FloatField(null=True, blank=True)
    current_deferred_revenue_q = models.FloatField(null=True, blank=True)
    current_deferred_tax_liability_q = models.FloatField(null=True, blank=True)
    current_capital_leases_q = models.FloatField(null=True, blank=True)
    other_current_liabilities_q = models.FloatField(null=True, blank=True)
    total_current_liabilities_q = models.FloatField(null=True, blank=True)
    lt_debt_q = models.FloatField(null=True, blank=True)
    noncurrent_capital_leases_q = models.FloatField(null=True, blank=True)
    pension_liabilities_q = models.FloatField(null=True, blank=True)
    noncurrent_deferred_revenue_q = models.FloatField(null=True, blank=True)
    other_lt_liabilities_q = models.FloatField(null=True, blank=True)
    total_liabilities_q = models.FloatField(null=True, blank=True)
    common_stock_q = models.FloatField(null=True, blank=True)
    preferred_stock_q = models.FloatField(null=True, blank=True)
    retained_earnings_q = models.FloatField(null=True, blank=True)
    aoci_q = models.FloatField(null=True, blank=True)
    apic_q = models.FloatField(null=True, blank=True)
    treasury_stock_q = models.FloatField(null=True, blank=True)
    other_equity_q = models.FloatField(null=True, blank=True)

    # CFO (Cash From Operations)
    cfo_net_income_y = models.FloatField(null=True, blank=True, verbose_name="Net Income (CFO)")
    cfo_da_y = models.FloatField(null=True, blank=True, verbose_name="Depreciation and Amortization (CFO)")
    cfo_receivables_y = models.FloatField(null=True, blank=True, verbose_name="Accounts Receivables (CFO)")
    cfo_inventory_y = models.FloatField(null=True, blank=True, verbose_name="Inventory (CFO)")
    cfo_prepaid_expenses_y = models.FloatField(null=True, blank=True, verbose_name="Prepaid Expenses (CFO)")
    cfo_other_working_capital_y = models.FloatField(null=True, blank=True, verbose_name="Other Working Capital (CFO)")
    cfo_change_in_working_capital_y = models.FloatField(null=True, blank=True, verbose_name="Change in Working Capital (CFO)")
    cfo_deferred_tax_y = models.FloatField(null=True, blank=True, verbose_name="Deferred Tax (CFO)")
    cfo_stock_comp_y = models.FloatField(null=True, blank=True, verbose_name="Stock Compensation (CFO)")
    cfo_other_noncash_items_y = models.FloatField(null=True, blank=True, verbose_name="Other Non-Cash items (CFO)")
    cf_cfo_y = models.FloatField(null=True, blank=True, verbose_name="Cash from Operations (CFO)")

    # CFI (Cash Flow from Investing)
    cfi_ppe_purchases_y = models.FloatField(null=True, blank=True, verbose_name="PP&E Purchases (CFI)")
    cfi_ppe_sales_y = models.FloatField(null=True, blank=True, verbose_name="PP&E Sales (CFI)")
    cfi_ppe_net_y = models.FloatField(null=True, blank=True, verbose_name="PP&E Net (CFI)")
    cfi_acquisitions_y = models.FloatField(null=True, blank=True, verbose_name="Acquisitions (CFI)")
    cfi_divestitures_y = models.FloatField(null=True, blank=True, verbose_name="Divestitures (CFI)")
    cfi_acquisitions_net_y = models.FloatField(null=True, blank=True, verbose_name="Acquisitions Net (CFI)")
    cfi_investment_purchases_y = models.FloatField(null=True, blank=True, verbose_name="Investment Purchases (CFI)")
    cfi_investment_sales_y = models.FloatField(null=True, blank=True, verbose_name="Investment Sales (CFI)")
    cfi_investment_net_y = models.FloatField(null=True, blank=True, verbose_name="Investments Net (CFI)")
    cfi_intangibles_net_y = models.FloatField(null=True, blank=True, verbose_name="Intangibles Net (CFI)")
    cfi_other_y = models.FloatField(null=True, blank=True, verbose_name="Other Investing Cash Flows (CFI)")
    cf_cfi_y = models.FloatField(null=True, blank=True, verbose_name="Cash from Investing (CFI)")

    # CFF (Cash Flow from Financing)
    cff_common_stock_issued_y = models.FloatField(null=True, blank=True, verbose_name="Common Stock Issued (CFF)")
    cff_common_stock_repurchased_y = models.FloatField(null=True, blank=True, verbose_name="Common Stock Repurchased (CFF)")
    cff_common_stock_net_y = models.FloatField(null=True, blank=True, verbose_name="Common Stock Net (CFF)")
    cff_pfd_issued_y = models.FloatField(null=True, blank=True, verbose_name="Preferred Stocks Issued (CFF)")
    cff_pfd_repurchased_y = models.FloatField(null=True, blank=True, verbose_name="Preferred Stocks Repurchased (CFF)")
    cff_pfd_net_y = models.FloatField(null=True, blank=True, verbose_name="Preferred Stocks Net (CFF)")
    cff_debt_issued_y = models.FloatField(null=True, blank=True, verbose_name="Debt Issued (CFF)")
    cff_debt_repaid_y = models.FloatField(null=True, blank=True, verbose_name="Debt Repaid (CFF)")
    cff_debt_net_y = models.FloatField(null=True, blank=True, verbose_name="Debt Net (CFF)")
    cff_dividend_paid_y = models.FloatField(null=True, blank=True, verbose_name="Dividend Paid (CFF)")
    cff_other_y = models.FloatField(null=True, blank=True, verbose_name="Other Financing Cash Flows (CFF)")
    cf_cff_y = models.FloatField(null=True, blank=True, verbose_name="Cash from Financing (CFF)")

    #annual key ratios
    market_cap_y = models.FloatField(null=True, blank=True, db_index=True, verbose_name="Market Capitalization")
    period_end_price_y = models.FloatField(null=True, blank=True, verbose_name="Period End Price")
    enterprise_value_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value (EV)")
    book_value_y = models.FloatField(null=True, blank=True, verbose_name="Book Value")
    tangible_book_value_y = models.FloatField(null=True, blank=True, verbose_name="Tangible Book Value")
    price_to_earnings_y = models.FloatField(null=True, blank=True, verbose_name="Price-to-Earnings (P/E)")
    price_to_book_y = models.FloatField(null=True, blank=True, verbose_name="Price-to-Book (P/B)")
    price_to_sales_y = models.FloatField(null=True, blank=True, verbose_name="Price-to-Sales (P/S)")
    price_to_tangible_book_y = models.FloatField(null=True, blank=True, verbose_name="Price-to-Tangible-Book-Value (PTBV)")
    price_to_fcf_y = models.FloatField(null=True, blank=True, verbose_name="Price to Free Cash Flow (P/FCF)")
    price_to_pretax_income_y = models.FloatField(null=True, blank=True, verbose_name="Price to Pretax Income")
    enterprise_value_to_earnings_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Earnings (EV/E)")
    enterprise_value_to_book_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Book (EV/B)")
    enterprise_value_to_tangible_book_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Tangible Book (EV/TB)")
    enterprise_value_to_sales_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Sales (EV/S)")
    enterprise_value_to_fcf_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Free Cash Flow (EV/FCF)")
    enterprise_value_to_pretax_income_y = models.FloatField(null=True, blank=True, verbose_name="Enterprise Value to Pretax Income")
    ebitda_y = models.FloatField(null=True, blank=True, verbose_name="EBITDA")
    capex_y = models.FloatField(null=True, blank=True, verbose_name="Capital Expenditures (Capex)")
    fcf_y = models.FloatField(null=True, blank=True, verbose_name="Free Cash Flow (FCF)")
    earning_assets_y = models.FloatField(null=True, blank=True, verbose_name="Earnings Assets")
    policy_revenue_y = models.FloatField(null=True, blank=True, verbose_name="Policy Revenue")
    underwriting_profit_y = models.FloatField(null=True, blank=True, verbose_name="Underwriting Profit")
    dividends_y = models.FloatField(null=True, blank=True, verbose_name="Dividends")
    payout_ratio_y = models.FloatField(null=True, blank=True, verbose_name="Payout Ratio")
    income_tax_rate_y = models.FloatField(null=True, blank=True, verbose_name="Income Tax Rate")
    net_debt_y = models.FloatField(null=True, blank=True, verbose_name="Net Debt")
    gross_margin_y = models.FloatField(null=True, blank=True, verbose_name="Gross Margin")
    ebitda_margin_y = models.FloatField(null=True, blank=True, verbose_name="EBITDA Margin")
    operating_margin_y = models.FloatField(null=True, blank=True, verbose_name="Operating Margin")
    pretax_margin_y = models.FloatField(null=True, blank=True, verbose_name="Pretax Margin")
    net_income_margin_y = models.FloatField(null=True, blank=True, verbose_name="Net Income Margin")
    fcf_margin_y = models.FloatField(null=True, blank=True, verbose_name="Free Cash Flow Margin")
    net_interest_margin_y = models.FloatField(null=True, blank=True, verbose_name="Net Interest Margin")
    underwriting_margin_y = models.FloatField(null=True, blank=True, verbose_name="Underwriting Margin")
    roe_y = models.FloatField(null=True, blank=True, verbose_name="Return on Equity (ROE)")
    roa_y = models.FloatField(null=True, blank=True, verbose_name="Return on Assets (ROA)")
    roic_y = models.FloatField(null=True, blank=True, verbose_name="Return on Invested Capital (ROIC)")
    roic_legacy_y = models.FloatField(null=True, blank=True, verbose_name="ROIC legacy")
    roce_y = models.FloatField(null=True, blank=True, verbose_name="Return on Capital Employed")
    rotce_y = models.FloatField(null=True, blank=True, verbose_name="Return on Tangible Capital Employed")
    roi_y = models.FloatField(null=True, blank=True, verbose_name="Return on Investment (ROI)")
    debt_to_equity_y = models.FloatField(null=True, blank=True, verbose_name="Debt to Equity")
    debt_to_assets_y = models.FloatField(null=True, blank=True, verbose_name="Debt to Assets")
    equity_to_assets_y = models.FloatField(null=True, blank=True, verbose_name="Equity to Assets")
    assets_to_equity_y = models.FloatField(null=True, blank=True, verbose_name="Assets to Equity")
    current_ratio_y = models.FloatField(null=True, blank=True, verbose_name="Current Ratio")
    earning_assets_to_equity_y = models.FloatField(null=True, blank=True, verbose_name="Earning Assets to Equity")
    loans_to_deposits_y = models.FloatField(null=True, blank=True, verbose_name="Loans to Deposits")
    loan_loss_reserve_to_loans_y = models.FloatField(null=True, blank=True, verbose_name="Loan Loss Reserve to Loans")
    revenue_per_share_y = models.FloatField(null=True, blank=True, verbose_name="Revenue per Share")
    ebitda_per_share_y = models.FloatField(null=True, blank=True, verbose_name="EBITDA per Share")
    operating_income_per_share_y = models.FloatField(null=True, blank=True, verbose_name="Operating Income per Share")
    pretax_income_per_share_y = models.FloatField(null=True, blank=True, verbose_name="Pretax Income per Share")
    fcf_per_share_y = models.FloatField(null=True, blank=True, verbose_name="FCF per Share")
    book_value_per_share_y = models.FloatField(null=True, blank=True, verbose_name="Book Value per Share")
    tangible_book_per_share_y = models.FloatField(null=True, blank=True, verbose_name="Tangible Book per Share")
    premiums_per_share_y = models.FloatField(null=True, blank=True, verbose_name="Premiums per Share")
    revenue_growth_y = models.FloatField(null=True, blank=True, verbose_name="Revenue Growth")
    gross_profit_growth_y = models.FloatField(null=True, blank=True, verbose_name="Gross Profit Growth")
    ebitda_growth_y = models.FloatField(null=True, blank=True, verbose_name="EBITDA Growth")
    operating_income_growth_y = models.FloatField(null=True, blank=True, verbose_name="Operating Income Growth")
    pretax_income_growth_y = models.FloatField(null=True, blank=True, verbose_name="Pretax Income Growth")
    net_income_growth_y = models.FloatField(null=True, blank=True, verbose_name="Net Income Growth")
    eps_diluted_growth_y = models.FloatField(null=True, blank=True, verbose_name="EPS diluted Growth")
    shares_diluted_growth_y = models.FloatField(null=True, blank=True, verbose_name="Shares Diluted Growth")
    shares_eop_growth_y = models.FloatField(null=True, blank=True, verbose_name="Shares EOP Growth")
    cash_and_equiv_growth_y = models.FloatField(null=True, blank=True, verbose_name="Cash and Equivalents Growth")
    ppe_growth_y = models.FloatField(null=True, blank=True, verbose_name="PP&E Growth")
    total_assets_growth_y = models.FloatField(null=True, blank=True, verbose_name="Total Assets Growth")
    total_equity_growth_y = models.FloatField(null=True, blank=True, verbose_name="Total Equity Growth")
    cfo_growth_y = models.FloatField(null=True, blank=True, verbose_name="Operating Cash Flow Growth")
    capex_growth_y = models.FloatField(null=True, blank=True, verbose_name="Capex Growth")
    fcf_growth_y = models.FloatField(null=True, blank=True, verbose_name="Free Cash Flow Growth")
    revenue_cagr_10_y = models.FloatField(null=True, blank=True, verbose_name="Revenue CAGR 10Y")
    eps_diluted_cagr_10_y = models.FloatField(null=True, blank=True, verbose_name="EPS diluted CAGR 10Y")
    total_assets_cagr_10_y = models.FloatField(null=True, blank=True, verbose_name="Total Assets CAGR 10Y")
    total_equity_cagr_10_y = models.FloatField(null=True, blank=True, verbose_name="Total Equity CAGR 10Y")
    cf_cfo_cagr_10_y = models.FloatField(null=True, blank=True, verbose_name="CFO CAGR 10Y")
    fcf_cagr_10_y = models.FloatField(null=True, blank=True, verbose_name="FCF CAGR 10Y")
    rnoa_y = models.FloatField(null=True, blank=True, verbose_name="RNOA")

    #key ratios quarterly
    market_cap_q = models.FloatField(null=True, blank=True, db_index=True)
    period_end_price_q = models.FloatField(null=True, blank=True)
    enterprise_value_q = models.FloatField(null=True, blank=True)
    book_value_q = models.FloatField(null=True, blank=True)
    tangible_book_value_q = models.FloatField(null=True, blank=True)
    price_to_earnings_q = models.FloatField(null=True, blank=True)
    price_to_book_q = models.FloatField(null=True, blank=True)
    price_to_sales_q = models.FloatField(null=True, blank=True)
    price_to_tangible_book_q = models.FloatField(null=True, blank=True)
    price_to_fcf_q = models.FloatField(null=True, blank=True)
    price_to_pretax_income_q = models.FloatField(null=True, blank=True)
    enterprise_value_to_earnings_q = models.FloatField(null=True, blank=True)
    enterprise_value_to_book_q = models.FloatField(null=True, blank=True)
    enterprise_value_to_tangible_book_q = models.FloatField(null=True, blank=True)
    enterprise_value_to_sales_q = models.FloatField(null=True, blank=True)
    enterprise_value_to_fcf_q = models.FloatField(null=True, blank=True)
    enterprise_value_to_pretax_income_q = models.FloatField(null=True, blank=True)
    ebitda_q = models.FloatField(null=True, blank=True)
    capex_q = models.FloatField(null=True, blank=True)
    fcf_q = models.FloatField(null=True, blank=True)
    earning_assets_q = models.FloatField(null=True, blank=True)
    policy_revenue_q = models.FloatField(null=True, blank=True)
    underwriting_profit_q = models.FloatField(null=True, blank=True)
    dividends_q = models.FloatField(null=True, blank=True)
    payout_ratio_q = models.FloatField(null=True, blank=True)
    income_tax_rate_q = models.FloatField(null=True, blank=True)
    net_debt_q = models.FloatField(null=True, blank=True)
    gross_margin_q = models.FloatField(null=True, blank=True)
    ebitda_margin_q = models.FloatField(null=True, blank=True)
    operating_margin_q = models.FloatField(null=True, blank=True)
    pretax_margin_q = models.FloatField(null=True, blank=True)
    net_income_margin_q = models.FloatField(null=True, blank=True)
    fcf_margin_q = models.FloatField(null=True, blank=True)
    net_interest_margin_q = models.FloatField(null=True, blank=True)
    underwriting_margin_q = models.FloatField(null=True, blank=True)
    roe_q = models.FloatField(null=True, blank=True)
    roa_q = models.FloatField(null=True, blank=True)
    roic_q = models.FloatField(null=True, blank=True)
    roic_legacy_q = models.FloatField(null=True, blank=True)
    roce_q = models.FloatField(null=True, blank=True)
    rotce_q = models.FloatField(null=True, blank=True)
    roi_q = models.FloatField(null=True, blank=True)
    debt_to_equity_q = models.FloatField(null=True, blank=True)
    equity_to_assets_q = models.FloatField(null=True, blank=True)
    debt_to_assets_q = models.FloatField(null=True, blank=True)
    assets_to_equity_q = models.FloatField(null=True, blank=True)
    current_ratio_q = models.FloatField(null=True, blank=True)
    earning_assets_to_equity_q = models.FloatField(null=True, blank=True)
    loans_to_deposits_q = models.FloatField(null=True, blank=True)
    loan_loss_reserve_to_loans_q = models.FloatField(null=True, blank=True)
    revenue_per_share_q = models.FloatField(null=True, blank=True)
    ebitda_per_share_q = models.FloatField(null=True, blank=True)
    operating_income_per_share_q = models.FloatField(null=True, blank=True)
    pretax_income_per_share_q = models.FloatField(null=True, blank=True)
    fcf_per_share_q = models.FloatField(null=True, blank=True)
    book_value_per_share_q = models.FloatField(null=True, blank=True)
    tangible_book_per_share_q = models.FloatField(null=True, blank=True)
    premiums_per_share_q = models.FloatField(null=True, blank=True)
    revenue_growth_q = models.FloatField(null=True, blank=True)
    gross_profit_growth_q = models.FloatField(null=True, blank=True)
    ebitda_growth_q = models.FloatField(null=True, blank=True)
    operating_income_growth_q = models.FloatField(null=True, blank=True)
    pretax_income_growth_q = models.FloatField(null=True, blank=True)
    net_income_growth_q = models.FloatField(null=True, blank=True)
    eps_diluted_growth_q = models.FloatField(null=True, blank=True)
    shares_diluted_growth_q = models.FloatField(null=True, blank=True)
    shares_eop_growth_q = models.FloatField(null=True, blank=True)
    cash_and_equiv_growth_q = models.FloatField(null=True, blank=True)
    ppe_growth_q = models.FloatField(null=True, blank=True)
    total_assets_growth_q = models.FloatField(null=True, blank=True)
    total_equity_growth_q = models.FloatField(null=True, blank=True)
    cfo_growth_q = models.FloatField(null=True, blank=True)
    capex_growth_q = models.FloatField(null=True, blank=True)
    fcf_growth_q = models.FloatField(null=True, blank=True)
    revenue_cagr_10_q = models.FloatField(null=True, blank=True)
    eps_diluted_cagr_10_q = models.FloatField(null=True, blank=True)
    total_assets_cagr_10_q = models.FloatField(null=True, blank=True)
    total_equity_cagr_10_q = models.FloatField(null=True, blank=True)
    cf_cfo_cagr_10_q = models.FloatField(null=True, blank=True)
    fcf_cagr_10_q = models.FloatField(null=True, blank=True)

    column_metadata = {
    #company info fields
    'ticker' : 'Company Info',
    'exchange' : 'Company Info',
    'name' : 'Company Info',
    'industry' : 'Company Info',
    'last_close_price' : 'Company Info',
    'currency' : 'Company Info',

    #valuation fields
    'epv_business': 'valuation',
    'epv_per_share': 'valuation',
    'epv_business_ttm': 'valuation',
    'epv_per_share_ttm': 'valuation',
    'penman_equity': 'valuation',
    'penman_per_share': 'valuation',
    'penman_g': 'valuation',
    'rnoa': 'valuation',
    'penman_equity_ttm': 'valuation',
    'penman_per_share_ttm': 'valuation',
    'penman_g_ttm': 'valuation',
    'rnoa_ttm': 'valuation',
    'price': 'valuation',

    #income statement annual
    'revenue_y': 'Income Statement (Y)',
    'cogs_y': 'Income Statement (Y)',
    'gross_profit_y': 'Income Statement (Y)',
    'sga_y': 'Income Statement (Y)',
    'rnd_y': 'Income Statement (Y)',
    'special_charges_y': 'Income Statement (Y)',
    'other_opex_y': 'Income Statement (Y)',
    'total_opex_y': 'Income Statement (Y)',
    'operating_income_y': 'Income Statement (Y)',
    'interest_income_y': 'Income Statement (Y)',
    'interest_expense_y': 'Income Statement (Y)',
    'net_interest_income_normal_y': 'Income Statement (Y)',
    'other_nonoperating_income_y': 'Income Statement (Y)',
    'pretax_income_y': 'Income Statement (Y)',
    'income_tax_y': 'Income Statement (Y)',
    'net_income_continuing_y': 'Income Statement (Y)',
    'net_income_discontinued_y': 'Income Statement (Y)',
    'income_allocated_to_minority_interest_y': 'Income Statement (Y)',
    'other_income_statement_items_y': 'Income Statement (Y)',
    'net_income_y': 'Income Statement (Y)',
    'preferred_dividends_y': 'Income Statement (Y)',
    'net_income_available_to_shareholders_y': 'Income Statement (Y)',
    'eps_basic_y': 'Income Statement (Y)',
    'eps_diluted_y': 'Income Statement (Y)',
    'shares_basic_y': 'Income Statement (Y)',
    'shares_diluted_y': 'Income Statement (Y)',
    'shares_eop_y': 'Income Statement (Y)',
    'shares_eop_change_y': 'Income Statement (Y)',

    #balance sheet annual
    'cash_and_equiv_y': 'Balance Sheet (Y)',
    'st_investments_y': 'Balance Sheet (Y)',
    'receivables_y': 'Balance Sheet (Y)',
    'inventories_y': 'Balance Sheet (Y)',
    'other_current_assets_y': 'Balance Sheet (Y)',
    'total_current_assets_y': 'Balance Sheet (Y)',
    'equity_and_other_investments_y': 'Balance Sheet (Y)',
    'ppe_gross_y': 'Balance Sheet (Y)',
    'accumulated_depreciation_y': 'Balance Sheet (Y)',
    'ppe_net_y': 'Balance Sheet (Y)',
    'intangible_assets_y': 'Balance Sheet (Y)',
    'goodwill_y': 'Balance Sheet (Y)',
    'other_lt_assets_y': 'Balance Sheet (Y)',
    'total_assets_y': 'Balance Sheet (Y)',
    'accounts_payable_y': 'Balance Sheet (Y)',
    'tax_payable_y': 'Balance Sheet (Y)',
    'current_accrued_liabilities_y': 'Balance Sheet (Y)',
    'st_debt_y': 'Balance Sheet (Y)',
    'current_deferred_revenue_y': 'Balance Sheet (Y)',
    'current_deferred_tax_liability_y': 'Balance Sheet (Y)',
    'current_capital_leases_y': 'Balance Sheet (Y)',
    'other_current_liabilities_y': 'Balance Sheet (Y)',
    'total_current_liabilities_y': 'Balance Sheet (Y)',
    'lt_debt_y': 'Balance Sheet (Y)',
    'noncurrent_capital_leases_y': 'Balance Sheet (Y)',
    'pension_liabilities_y': 'Balance Sheet (Y)',
    'noncurrent_deferred_revenue_y': 'Balance Sheet (Y)',
    'other_lt_liabilities_y': 'Balance Sheet (Y)',
    'total_liabilities_y': 'Balance Sheet (Y)',
    'common_stock_y': 'Balance Sheet (Y)',
    'preferred_stock_y': 'Balance Sheet (Y)',
    'retained_earnings_y': 'Balance Sheet (Y)',
    'aoci_y': 'Balance Sheet (Y)',
    'apic_y': 'Balance Sheet (Y)',
    'treasury_stock_y': 'Balance Sheet (Y)',
    'other_equity_y': 'Balance Sheet (Y)',
    'minority_interest_liability_y': 'Balance Sheet (Y)',
    'total_equity_y': 'Balance Sheet (Y)',
    'total_liabilities_and_equity_y': 'Balance Sheet (Y)',

    #balance sheet quarterly
    'cash_and_equiv_q': 'Balance Sheet (Q)',
    'st_investments_q': 'Balance Sheet (Q)',
    'receivables_q': 'Balance Sheet (Q)',
    'inventories_q': 'Balance Sheet (Q)',
    'other_current_assets_q': 'Balance Sheet (Q)',
    'total_current_assets_q': 'Balance Sheet (Q)',
    'equity_and_other_investments_q': 'Balance Sheet (Q)',
    'ppe_gross_q': 'Balance Sheet (Q)',
    'accumulated_depreciation_q': 'Balance Sheet (Q)',
    'ppe_net_q': 'Balance Sheet (Q)',
    'intangible_assets_q': 'Balance Sheet (Q)',
    'goodwill_q': 'Balance Sheet (Q)',
    'other_lt_assets_q': 'Balance Sheet (Q)',
    'total_assets_q': 'Balance Sheet (Q)',
    'accounts_payable_q': 'Balance Sheet (Q)',
    'tax_payable_q': 'Balance Sheet (Q)',
    'current_accrued_liabilities_q': 'Balance Sheet (Q)',
    'st_debt_q': 'Balance Sheet (Q)',
    'current_deferred_revenue_q': 'Balance Sheet (Q)',
    'current_deferred_tax_liability_q': 'Balance Sheet (Q)',
    'current_capital_leases_q': 'Balance Sheet (Q)',
    'other_current_liabilities_q': 'Balance Sheet (Q)',
    'total_current_liabilities_q': 'Balance Sheet (Q)',
    'lt_debt_q': 'Balance Sheet (Q)',
    'noncurrent_capital_leases_q': 'Balance Sheet (Q)',
    'pension_liabilities_q': 'Balance Sheet (Q)',
    'noncurrent_deferred_revenue_q': 'Balance Sheet (Q)',
    'other_lt_liabilities_q': 'Balance Sheet (Q)',
    'total_liabilities_q': 'Balance Sheet (Q)',
    'common_stock_q': 'Balance Sheet (Q)',
    'preferred_stock_q': 'Balance Sheet (Q)',
    'retained_earnings_q': 'Balance Sheet (Q)',
    'aoci_q': 'Balance Sheet (Q)',
    'apic_q': 'Balance Sheet (Q)',
    'treasury_stock_q': 'Balance Sheet (Q)',
    'other_equity_q': 'Balance Sheet (Q)',

    # CFO (Cash Flow from Operations)
    'cfo_net_income_y': 'Cashflow Statement (Y)',
    'cfo_da_y': 'Cashflow Statement (Y)',
    'cfo_receivables_y': 'Cashflow Statement (Y)',
    'cfo_inventory_y': 'Cashflow Statement (Y)',
    'cfo_prepaid_expenses_y': 'Cashflow Statement (Y)',
    'cfo_other_working_capital_y': 'Cashflow Statement (Y)',
    'cfo_change_in_working_capital_y': 'Cashflow Statement (Y)',
    'cfo_deferred_tax_y': 'Cashflow Statement (Y)',
    'cfo_stock_comp_y': 'Cashflow Statement (Y)',
    'cfo_other_noncash_items_y': 'Cashflow Statement (Y)',
    'cf_cfo_y': 'Cashflow Statement (Y)',

    # CFI (Cash Flow from Investing)
    'cfi_ppe_purchases_y': 'Cashflow Statement (Y)',
    'cfi_ppe_sales_y': 'Cashflow Statement (Y)',
    'cfi_ppe_net_y': 'Cashflow Statement (Y)',
    'cfi_acquisitions_y': 'Cashflow Statement (Y)',
    'cfi_divestitures_y': 'Cashflow Statement (Y)',
    'cfi_acquisitions_net_y': 'Cashflow Statement (Y)',
    'cfi_investment_purchases_y': 'Cashflow Statement (Y)',
    'cfi_investment_sales_y': 'Cashflow Statement (Y)',
    'cfi_investment_net_y': 'Cashflow Statement (Y)',
    'cfi_intangibles_net_y': 'Cashflow Statement (Y)',
    'cfi_other_y': 'Cashflow Statement (Y)',
    'cf_cfi_y': 'Cashflow Statement (Y)',

    # CFF (Cash Flow from Financing)
    'cff_common_stock_issued_y': 'Cashflow Statement (Y)',
    'cff_common_stock_repurchased_y': 'Cashflow Statement (Y)',
    'cff_common_stock_net_y': 'Cashflow Statement (Y)',
    'cff_pfd_issued_y': 'Cashflow Statement (Y)',
    'cff_pfd_repurchased_y': 'Cashflow Statement (Y)',
    'cff_pfd_net_y': 'Cashflow Statement (Y)',
    'cff_debt_issued_y': 'Cashflow Statement (Y)',
    'cff_debt_repaid_y': 'Cashflow Statement (Y)',
    'cff_debt_net_y': 'Cashflow Statement (Y)',
    'cff_dividend_paid_y': 'Cashflow Statement (Y)',
    'cff_other_y': 'Cashflow Statement (Y)',
    'cf_cff_y': 'Cashflow Statement (Y)',

    #Key Ratios Annual
    'market_cap_y': 'Key Ratios (Y)',
    'period_end_price_y': 'Key Ratios (Y)',
    'enterprise_value_y': 'Key Ratios (Y)',
    'book_value_y': 'Key Ratios (Y)',
    'tangible_book_value_y': 'Key Ratios (Y)',
    'price_to_earnings_y': 'Key Ratios (Y)',
    'price_to_book_y': 'Key Ratios (Y)',
    'price_to_sales_y': 'Key Ratios (Y)',
    'price_to_tangible_book_y': 'Key Ratios (Y)',
    'price_to_fcf_y': 'Key Ratios (Y)',
    'price_to_pretax_income_y': 'Key Ratios (Y)',
    'enterprise_value_to_earnings_y': 'Key Ratios (Y)',
    'enterprise_value_to_book_y': 'Key Ratios (Y)',
    'enterprise_value_to_tangible_book_y': 'Key Ratios (Y)',
    'enterprise_value_to_sales_y': 'Key Ratios (Y)',
    'enterprise_value_to_fcf_y': 'Key Ratios (Y)',
    'enterprise_value_to_pretax_income_y': 'Key Ratios (Y)',
    'ebitda_y': 'Key Ratios (Y)',
    'capex_y': 'Key Ratios (Y)',
    'fcf_y': 'Key Ratios (Y)',
    'earning_assets_y': 'Key Ratios (Y)',
    'policy_revenue_y': 'Key Ratios (Y)',
    'underwriting_profit_y': 'Key Ratios (Y)',
    'dividends_y': 'Key Ratios (Y)',
    'payout_ratio_y': 'Key Ratios (Y)',
    'income_tax_rate_y': 'Key Ratios (Y)',
    'net_debt_y': 'Key Ratios (Y)',
    'gross_margin_y': 'Key Ratios (Y)',
    'ebitda_margin_y': 'Key Ratios (Y)',
    'operating_margin_y': 'Key Ratios (Y)',
    'pretax_margin_y': 'Key Ratios (Y)',
    'net_income_margin_y': 'Key Ratios (Y)',
    'fcf_margin_y': 'Key Ratios (Y)',
    'net_interest_margin_y': 'Key Ratios (Y)',
    'underwriting_margin_y': 'Key Ratios (Y)',
    'roe_y': 'Key Ratios (Y)',
    'roa_y': 'Key Ratios (Y)',
    'roic_y': 'Key Ratios (Y)',
    'roic_legacy_y': 'Key Ratios (Y)',
    'roce_y': 'Key Ratios (Y)',
    'rotce_y': 'Key Ratios (Y)',
    'roi_y': 'Key Ratios (Y)',
    'debt_to_equity_y': 'Key Ratios (Y)',
    'debt_to_assets_y': 'Key Ratios (Y)',
    'equity_to_assets_y': 'Key Ratios (Y)',
    'assets_to_equity_y': 'Key Ratios (Y)',
    'current_ratio_y': 'Key Ratios (Y)',
    'earning_assets_to_equity_y': 'Key Ratios (Y)',
    'loans_to_deposits_y': 'Key Ratios (Y)',
    'loan_loss_reserve_to_loans_y': 'Key Ratios (Y)',
    'revenue_per_share_y': 'Key Ratios (Y)',
    'ebitda_per_share_y': 'Key Ratios (Y)',
    'operating_income_per_share_y': 'Key Ratios (Y)',
    'pretax_income_per_share_y': 'Key Ratios (Y)',
    'fcf_per_share_y': 'Key Ratios (Y)',
    'book_value_per_share_y': 'Key Ratios (Y)',
    'tangible_book_per_share_y': 'Key Ratios (Y)',
    'premiums_per_share_y': 'Key Ratios (Y)',
    'revenue_growth_y': 'Key Ratios (Y)',
    'gross_profit_growth_y': 'Key Ratios (Y)',
    'ebitda_growth_y': 'Key Ratios (Y)',
    'operating_income_growth_y': 'Key Ratios (Y)',
    'pretax_income_growth_y': 'Key Ratios (Y)',
    'net_income_growth_y': 'Key Ratios (Y)',
    'eps_diluted_growth_y': 'Key Ratios (Y)',
    'shares_diluted_growth_y': 'Key Ratios (Y)',
    'shares_eop_growth_y': 'Key Ratios (Y)',
    'cash_and_equiv_growth_y': 'Key Ratios (Y)',
    'ppe_growth_y': 'Key Ratios (Y)',
    'total_assets_growth_y': 'Key Ratios (Y)',
    'total_equity_growth_y': 'Key Ratios (Y)',
    'cfo_growth_y': 'Key Ratios (Y)',
    'capex_growth_y': 'Key Ratios (Y)',
    'fcf_growth_y': 'Key Ratios (Y)',
    'revenue_cagr_10_y': 'Key Ratios (Y)',
    'eps_diluted_cagr_10_y': 'Key Ratios (Y)',
    'total_assets_cagr_10_y': 'Key Ratios (Y)',
    'total_equity_cagr_10_y': 'Key Ratios (Y)',
    'cf_cfo_cagr_10_y': 'Key Ratios (Y)',
    'fcf_cagr_10_y': 'Key Ratios (Y)',
    'rnoa_y': 'Key Ratios (Y)',

    #Key ratios quarterly
    "market_cap_q": "Key Ratios (Q)",
    "period_end_price_q": "Key Ratios (Q)",
    "enterprise_value_q": "Key Ratios (Q)",
    "book_value_q": "Key Ratios (Q)",
    "tangible_book_value_q": "Key Ratios (Q)",
    "price_to_earnings_q": "Key Ratios (Q)",
    "price_to_book_q": "Key Ratios (Q)",
    "price_to_sales_q": "Key Ratios (Q)",
    "price_to_tangible_book_q": "Key Ratios (Q)",
    "price_to_fcf_q": "Key Ratios (Q)",
    "price_to_pretax_income_q": "Key Ratios (Q)",
    "enterprise_value_to_earnings_q": "Key Ratios (Q)",
    "enterprise_value_to_book_q": "Key Ratios (Q)",
    "enterprise_value_to_tangible_book_q": "Key Ratios (Q)",
    "enterprise_value_to_sales_q": "Key Ratios (Q)",
    "enterprise_value_to_fcf_q": "Key Ratios (Q)",
    "enterprise_value_to_pretax_income_q": "Key Ratios (Q)",
    "ebitda_q": "Key Ratios (Q)",
    "capex_q": "Key Ratios (Q)",
    "fcf_q": "Key Ratios (Q)",
    "earning_assets_q": "Key Ratios (Q)",
    "policy_revenue_q": "Key Ratios (Q)",
    "underwriting_profit_q": "Key Ratios (Q)",
    "dividends_q": "Key Ratios (Q)",
    "payout_ratio_q": "Key Ratios (Q)",
    "income_tax_rate_q": "Key Ratios (Q)",
    "net_debt_q": "Key Ratios (Q)",
    "gross_margin_q": "Key Ratios (Q)",
    "ebitda_margin_q": "Key Ratios (Q)",
    "operating_margin_q": "Key Ratios (Q)",
    "pretax_margin_q": "Key Ratios (Q)",
    "net_income_margin_q": "Key Ratios (Q)",
    "fcf_margin_q": "Key Ratios (Q)",
    "net_interest_margin_q": "Key Ratios (Q)",
    "underwriting_margin_q": "Key Ratios (Q)",
    "roe_q": "Key Ratios (Q)",
    "roa_q": "Key Ratios (Q)",
    "roic_q": "Key Ratios (Q)",
    "roic_legacy_q": "Key Ratios (Q)",
    "roce_q": "Key Ratios (Q)",
    "rotce_q": "Key Ratios (Q)",
    "roi_q": "Key Ratios (Q)",
    "debt_to_equity_q": "Key Ratios (Q)",
    "equity_to_assets_q": "Key Ratios (Q)",
    "debt_to_assets_q": "Key Ratios (Q)",
    "assets_to_equity_q": "Key Ratios (Q)",
    "current_ratio_q": "Key Ratios (Q)",
    "earning_assets_to_equity_q": "Key Ratios (Q)",
    "loans_to_deposits_q": "Key Ratios (Q)",
    "loan_loss_reserve_to_loans_q": "Key Ratios (Q)",
    "revenue_per_share_q": "Key Ratios (Q)",
    "ebitda_per_share_q": "Key Ratios (Q)",
    "operating_income_per_share_q": "Key Ratios (Q)",
    "pretax_income_per_share_q": "Key Ratios (Q)",
    "fcf_per_share_q": "Key Ratios (Q)",
    "book_value_per_share_q": "Key Ratios (Q)",
    "tangible_book_per_share_q": "Key Ratios (Q)",
    "premiums_per_share_q": "Key Ratios (Q)",
    "revenue_growth_q": "Key Ratios (Q)",
    "gross_profit_growth_q": "Key Ratios (Q)",
    "ebitda_growth_q": "Key Ratios (Q)",
    "operating_income_growth_q": "Key Ratios (Q)",
    "pretax_income_growth_q": "Key Ratios (Q)",
    "net_income_growth_q": "Key Ratios (Q)",
    "eps_diluted_growth_q": "Key Ratios (Q)",
    "shares_diluted_growth_q": "Key Ratios (Q)",
    "shares_eop_growth_q": "Key Ratios (Q)",
    "cash_and_equiv_growth_q": "Key Ratios (Q)",
    "ppe_growth_q": "Key Ratios (Q)",
    "total_assets_growth_q": "Key Ratios (Q)",
    "total_equity_growth_q": "Key Ratios (Q)",
    "cfo_growth_q": "Key Ratios (Q)",
    "capex_growth_q": "Key Ratios (Q)",
    "fcf_growth_q": "Key Ratios (Q)",
    "revenue_cagr_10_q": "Key Ratios (Q)",
    "eps_diluted_cagr_10_q": "Key Ratios (Q)",
    "total_assets_cagr_10_q": "Key Ratios (Q)",
    "total_equity_cagr_10_q": "Key Ratios (Q)",
    "cf_cfo_cagr_10_q": "Key Ratios (Q)",
    "fcf_cagr_10_q": "Key Ratios (Q)"

    }

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['qfs_symbol'], name="unique_qfs_symbol")
        ]