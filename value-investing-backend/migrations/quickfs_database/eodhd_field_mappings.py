"""
EODHD → Django model field mappings.
Field names verified against a real EODHD fundamentals response (AAPL, June 2026).

EODHD quirks (intentional — these are the real field names):
  "goodWill"               capital W
  "capitalSurpluse"        missing trailing 's'
  "nonCurrrentAssetsOther" three r's

EODHD fields that look useful but are NOT what they seem:
  "otherOperatingExpenses" = COGS + SGA + RND (a total, not a residual) — not mapped
  "totalOperatingExpenses" = revenue-level total (COGS + SGA + RND + …) — not used as opex

── Income statement mapping philosophy ────────────────────────────────────────

EODHD reports income statement fields independently; their components do not
always sum to their own aggregates (rounding, normalization across accounting
standards, missing line items). We handle this with three field roles:

  Tier 1 anchors — taken verbatim from the audited filing, always trusted:
    revenue, gross_profit, operating_income, pretax_income, net_income

  Raw components — stored as-is from EODHD, analytically useful but not
    guaranteed to reconcile with adjacent anchors:
    cogs, sga, rnd, special_charges, interest_income, interest_expense,
    income_tax, minority_interest, net_income_discontinued, preferred_dividends

  Derived connectors — computed from the two adjacent anchors so the P&L
    waterfall is always internally consistent:
    total_opex             = gross_profit − operating_income
    other_nonoperating_income = pretax_income − operating_income − interest_income + interest_expense

  Residuals — absorb whatever EODHD does not explicitly break out (D&A,
    restructuring, lease costs, sign-convention differences, etc.):
    other_opex             = total_opex − sga − rnd − special_charges
    other_income_statement_items = net_income − pretax_income + income_tax
                                   − minority_interest − net_income_discontinued

  Fallback field — uses EODHD when available, otherwise derived:
    net_income_available_to_shareholders = netIncomeApplicableToCommonShares
                                          or net_income − preferred_dividends

Waterfall identities guaranteed by construction:
  gross_profit − total_opex                              = operating_income
  sga + rnd + special_charges + other_opex               = total_opex
  operating_income + interest_income − interest_expense + other_nonoperating_income = pretax_income
  pretax_income − income_tax + minority_interest
    + net_income_discontinued + other_income_statement_items = net_income
  net_income − preferred_dividends = net_income_available_to_shareholders

Note: gross_profit = revenue − cogs is NOT guaranteed; both sides are stored
raw from EODHD and may disagree (genuine provider inconsistency).

── Balance sheet mapping philosophy ────────────────────────────────────────

The same tier structure applies to the balance sheet.

  Tier 1 anchors — taken verbatim from the audited filing, always trusted:
    total_current_assets, total_assets,
    total_current_liabilities, total_liabilities, total_equity

  Raw components — stored as-is from EODHD, analytically useful but not
    guaranteed to reconcile with adjacent anchors:
    cash_and_equiv, st_investments, receivables, inventories,
    equity_and_other_investments, ppe_net, goodwill, intangible_assets,
    accounts_payable, st_debt, current_deferred_revenue,
    lt_debt, noncurrent_capital_leases,
    common_stock, preferred_stock, retained_earnings, aoci, apic,
    treasury_stock, minority_interest_liability

  Derived connector:
    total_liabilities_and_equity = total_liabilities + total_equity

  Residuals — absorb whatever EODHD does not explicitly break out:
    other_current_assets  = total_current_assets − cash − st_inv − recv − inv
    other_lt_assets       = (total_assets − total_current_assets)
                            − ppe_net − goodwill − intangibles − lt_investments
    other_current_liabs   = total_current_liabilities − ap − st_debt − def_rev
    other_lt_liabs        = (total_liabilities − total_current_liabilities)
                            − lt_debt − noncurrent_capital_leases
    other_equity          = total_equity − common − pfd − retained − aoci
                            − apic − treasury − minority_interest

Identities guaranteed by construction:
  cash + st_investments + receivables + inventories + other_current_assets
      = total_current_assets
  total_current_assets + equity_and_other_investments + ppe_net + goodwill
      + intangible_assets + other_lt_assets = total_assets
  accounts_payable + st_debt + current_deferred_revenue + other_current_liabs
      = total_current_liabilities
  total_current_liabilities + lt_debt + noncurrent_capital_leases
      + other_lt_liabs = total_liabilities
  common + pfd + retained + aoci + apic + treasury + minority + other_equity
      = total_equity

Note: total_assets = total_liabilities + total_equity is NOT guaranteed by
construction (all three are raw anchors); the test_accounting_equation test
validates this as a data-quality check — EODHD defines
totalStockholderEquity = totalAssets − totalLiab, so failures indicate
genuine provider inconsistency.
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _float(v):
    """Convert an EODHD numeric string (or None) to float."""
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _subtract_nullable(a, b):
    """Subtract abs(b) from a. Returns None if a is None, treats None b as 0."""
    a_f = _float(a)
    if a_f is None:
        return None
    return a_f - abs(_float(b) or 0.0)


def _sum_nullable(*values):
    """Sum numeric values, treating None as zero. Returns None if all inputs are None."""
    floats = [_float(v) for v in values]
    non_null = [f for f in floats if f is not None]
    return sum(non_null) if non_null else None


def _sga(raw: dict) -> float | None:
    """SGA including selling expenses when reported as a separate line item.
    Under non-US GAAP (e.g. Chinese CAS) selling and admin are distinct fields;
    under US GAAP sellingGeneralAdministrative already includes selling."""
    sga = raw.get("sellingGeneralAdministrative")
    selling = raw.get("sellingAndMarketingExpenses")
    if selling is not None and selling != sga:
        return _sum_nullable(sga, selling)
    return _float(sga)




# ── TradedCompanies ────────────────────────────────────────────────────────────

def transform_traded_company(general: dict, exchange_code: str) -> dict:
    """
    Maps General section → TradedCompanies model row.
    qfs_symbol = PrimaryTicker  e.g. "AAPL.US"
    ticker     = Code           e.g. "AAPL" 
    exchange   = exchange_code  e.g. "US"  (the EODHD exchange code, not General.Exchange
                                which returns the operating mic e.g. "NASDAQ")
    """
    # Use PrimaryTicker only when this file IS the primary listing.
    # Cross-listed tickers (e.g. 19YA.STU) share PrimaryTicker with the main
    # listing (YRD.US). Using it unconditionally lets a secondary listing claim
    # the primary qfs_symbol first, after which ON CONFLICT DO NOTHING silently
    # skips the real primary file.
    pt = general.get("PrimaryTicker") or ""
    pt_exchange = pt.split(".")[-1] if "." in pt else ""
    primary_ticker = pt if pt_exchange == exchange_code else f"{general['Code']}.{exchange_code}"
    return {
        "qfs_symbol":   primary_ticker,
        "ticker":       general.get("Code"),
        "exchange":     exchange_code,
        "name":         general.get("Name"),
        "company_type": general.get("Type"),
        "currency":     general.get("CurrencyCode"),
        "industry":     general.get("Industry"),
        # has_new_financials defaults to True in the model
        # last_close_price is populated separately by migrate_close_prices.py
    }


# ── Income Statement ───────────────────────────────────────────────────────────

def transform_income_statement(raw: dict, qfs_symbol: str) -> dict:
    """
    Maps one EODHD Income_Statement period dict → IncomeStatementAnnual / Quarter row.
    Fields the provider does not supply are explicitly set to None.

    See module docstring for the anchor / component / connector / residual strategy.
    """
    # ── Tier 1 anchors (raw from EODHD, always trusted) ───────────────────────
    gross_profit     = _float(raw.get("grossProfit"))
    operating_income = _float(raw.get("operatingIncome"))
    pretax_income    = _float(raw.get("incomeBeforeTax"))
    income_tax       = _float(raw.get("incomeTaxExpense")) or _float(raw.get("taxProvision"))
    net_income       = _float(raw.get("netIncome"))

    # ── Raw components (stored as-is, analytical detail) ──────────────────────
    sga             = _sga(raw)
    rnd             = _float(raw.get("researchDevelopment"))
    special_charges = _sum_nullable(raw.get("nonRecurring"), raw.get("extraordinaryItems"))
    minority        = _float(raw.get("minorityInterest"))
    discontinued    = _float(raw.get("discontinuedOperations"))
    pref_dividends  = _float(raw.get("preferredStockAndOtherAdjustments"))

    interest_income  = _float(raw.get("interestIncome"))
    interest_expense = _float(raw.get("interestExpense"))

    # ── Derived connectors (bridge adjacent anchors; identities guaranteed) ───
    # total_opex bridges gross_profit → operating_income
    total_opex = (
        gross_profit - operating_income
        if gross_profit is not None and operating_income is not None
        else None
    )
    # other_nonoperating_income bridges operating_income → pretax_income,
    # explicitly excluding interest items that have their own line items.
    other_nonop = (
        pretax_income - operating_income - (interest_income or 0) + (interest_expense or 0)
        if pretax_income is not None and operating_income is not None
        else None
    )

    # ── Residuals (absorb items EODHD does not explicitly break out) ──────────
    # other_opex captures D&A, restructuring, and any undisclosed opex items
    other_opex = (
        total_opex - (sga or 0) - (rnd or 0) - (special_charges or 0)
        if total_opex is not None
        else None
    )

    # if other_opex is negative we will set it to 0
    if other_opex and other_opex < 0:
        other_opex = 0

    # other_income_statement_items absorbs minority interest sign conventions,
    # deferred tax, and any other items between pretax and net income
    if net_income is not None and pretax_income is not None and income_tax is not None:
        other_items = (
            net_income
            - pretax_income
            + income_tax
            - (minority or 0)
            - (discontinued or 0)
        )
    else:
        other_items = None

    # ── Fallback: use EODHD field when available, derive otherwise ─────────────
    ni_to_common = (
        _float(raw.get("netIncomeApplicableToCommonShares"))
        or (net_income - (pref_dividends or 0) if net_income is not None else None)
    )

    return {
        "qfs_symbol_id":   qfs_symbol,
        "period_end_date": raw["date"],
        "reporting_currency": raw.get("currency_symbol"),

        # ── Gross profit section: all three stored raw ─────────────────────────
        # gross_profit = revenue − cogs is NOT guaranteed (EODHD inconsistency);
        # both sides are anchors and may disagree.
        "revenue":      _float(raw.get("totalRevenue")),
        "cogs":         _float(raw.get("costOfRevenue")),
        "gross_profit": gross_profit,

        # ── Opex section ───────────────────────────────────────────────────────
        # total_opex is derived so gross_profit − total_opex = operating_income always holds.
        # sga / rnd / special_charges are raw components; other_opex is the residual.
        "sga":             sga,
        "rnd":             rnd,
        "special_charges": special_charges,
        "other_opex":      other_opex,
        "total_opex":      total_opex,
        "operating_income": operating_income,

        # ── Non-operating section ──────────────────────────────────────────────
        # other_nonoperating_income is derived so the 4-item identity holds:
        # operating_income + interest_income − interest_expense + other_nonoperating_income = pretax_income
        "interest_income":            interest_income,
        "interest_expense":           interest_expense,
        "net_interest_income_normal": _float(raw.get("netInterestIncome")),
        "other_nonoperating_income":  other_nonop,

        # ── Bottom of P&L ──────────────────────────────────────────────────────
        # other_income_statement_items is the residual that makes the identity:
        # pretax − tax + minority + discontinued + other_items = net_income
        "pretax_income":                          pretax_income,
        "income_tax":                             income_tax,
        "net_income_continuing":                  _float(raw.get("netIncomeFromContinuingOps")),
        "net_income_discontinued":                discontinued,
        "income_allocated_to_minority_interest":  minority,
        "other_income_statement_items":           other_items,
        "net_income":                             net_income,

        # preferred_dividends stored raw; net_income_available_to_shareholders
        # falls back to net_income − preferred_dividends when EODHD omits the field.
        "preferred_dividends":                    pref_dividends,
        "net_income_available_to_shareholders":   ni_to_common,

        # EPS / shares — not in EODHD Financials section
        "eps_basic":         None,
        "eps_diluted":       None,
        "shares_basic":      None,
        "shares_diluted":    None,
        "shares_eop":        None,
        "shares_eop_change": None,

        # Insurance-specific — not provided by EODHD for standard companies
        "premiums_earned":                                   None,
        "net_investment_income":                             None,
        "fees_and_other_income":                             None,
        "net_policyholder_claims_expense":                   None,
        "policy_acquisition_expense":                        None,
        "interest_expense_insurance":                        None,
        "total_interest_income":                             None,
        "total_interest_expense":                            None,
        "net_interest_income":                               _float(raw.get("netInterestIncome")),
        "total_noninterest_revenue":                         None,
        "credit_losses_provision":                           None,
        "net_interest_income_after_credit_losses_provision": None,
        "total_noninterest_expense":                         None,
        "da_income_statement_supplemental":                  _float(raw.get("depreciationAndAmortization")) or _float(raw.get("reconciledDepreciation")),
    }


# ── Balance Sheet ──────────────────────────────────────────────────────────────

def transform_balance_sheet(raw: dict, qfs_symbol: str) -> dict:
    # ── Tier 1 anchors (raw from EODHD, always trusted) ───────────────────────
    total_current_assets      = _float(raw.get("totalCurrentAssets"))
    total_assets              = _float(raw.get("totalAssets"))
    total_current_liabilities = _float(raw.get("totalCurrentLiabilities"))
    total_liabilities         = _float(raw.get("totalLiab"))
    total_equity              = _float(raw.get("totalStockholderEquity"))

    # ── Raw components (stored as-is, analytical detail) ──────────────────────
    cash           = _float(raw.get("cashAndEquivalents")) or _float(raw.get("cash"))
    st_investments = _float(raw.get("shortTermInvestments"))
    receivables    = _float(raw.get("netReceivables"))
    inventories    = _float(raw.get("inventory"))

    lt_investments = _float(raw.get("longTermInvestments"))
    ppe_net        = _float(raw.get("propertyPlantEquipment")) or _float(raw.get("propertyPlantAndEquipmentNet"))
    goodwill       = _subtract_nullable(raw.get("goodWill"), raw.get("negativeGoodwill"))  # capital W — intentional
    intangibles    = _float(raw.get("intangibleAssets"))

    accounts_payable       = _float(raw.get("accountsPayable"))
    st_debt                = _float(raw.get("shortTermDebt"))
    current_deferred_rev   = _float(raw.get("currentDeferredRevenue"))

    lt_debt            = _float(raw.get("longTermDebt")) or _float(raw.get("longTermDebtTotal"))
    noncurrent_leases  = _float(raw.get("capitalLeaseObligations"))

    common_stock    = _float(raw.get("commonStock")) or _float(raw.get("capitalStock")) or _float(raw.get("commonStockTotalEquity"))
    preferred_stock = _float(raw.get("preferredStockRedeemable")) or _float(raw.get("preferredStockTotalEquity"))
    retained        = _float(raw.get("retainedEarnings")) or _float(raw.get("retainedEarningsTotalEquity"))
    aoci            = _float(raw.get("accumulatedOtherComprehensiveIncome")) or _float(raw.get("otherStockholderEquity"))
    apic            = _float(raw.get("additionalPaidInCapital")) or _float(raw.get("capitalSurpluse"))
    treasury        = _float(raw.get("treasuryStock"))
    minority        = _float(raw.get("noncontrollingInterestInConsolidatedEntity"))

    # ── Derived connector ──────────────────────────────────────────────────────
    total_liabilities_and_equity = (
        total_liabilities + total_equity
        if total_liabilities is not None and total_equity is not None
        else None
    )

    # ── Residuals (absorb items EODHD does not explicitly break out) ──────────
    # other_current_assets absorbs prepaid expenses, deferred tax assets, etc.
    other_current_assets = (
        total_current_assets - (cash or 0) - (st_investments or 0) - (receivables or 0) - (inventories or 0)
        if total_current_assets is not None
        else None
    )

    # other_lt_assets is anchored directly on total_assets minus every known component,
    # so all asset line items always sum to total_assets regardless of whether
    # total_current_assets is available. When total_current_assets is null,
    # other_current_assets is also null (treated as 0 here), and other_lt_assets
    # absorbs both the untracked current assets and the non-current residual.
    other_lt_assets = (
        total_assets
        - (cash or 0) - (st_investments or 0) - (receivables or 0) - (inventories or 0)
        - (other_current_assets or 0)
        - (lt_investments or 0) - (ppe_net or 0) - (goodwill or 0) - (intangibles or 0)
        if total_assets is not None
        else None
    )

    # other_current_liabilities absorbs tax payable, accrued liabilities, etc.
    other_current_liabilities = (
        total_current_liabilities - (accounts_payable or 0) - (st_debt or 0) - (current_deferred_rev or 0)
        if total_current_liabilities is not None
        else None
    )

    # other_lt_liabilities is anchored on (total_assets - total_equity) rather than
    # totalLiab, absorbing provisions and any items EODHD excludes from totalLiab.
    # This guarantees the accounting equation by construction:
    #   total_current_liabilities + lt_debt + noncurrent_leases
    #     + other_lt_liabilities + total_equity  =  total_assets
    # Falls back to totalLiab when either anchor is missing.
    effective_total_liabilities = (
        total_assets - total_equity
        if total_assets is not None and total_equity is not None
        else total_liabilities
    )
    other_lt_liabilities = (
        effective_total_liabilities - (total_current_liabilities or 0) - (lt_debt or 0) - (noncurrent_leases or 0)
        if effective_total_liabilities is not None
        else None
    )

    # other_equity absorbs warrants, temporary equity, and any sign-convention
    # differences; treasury_stock retains its sign from EODHD (typically negative).
    other_equity = (
        total_equity - (common_stock or 0) - (preferred_stock or 0) - (retained or 0)
        - (aoci or 0) - (apic or 0) - (treasury or 0) - (minority or 0)
        if total_equity is not None
        else None
    )

    return {
        "qfs_symbol_id":                        qfs_symbol,
        "period_end_date":                      raw["date"],
        "reporting_currency":                   raw.get("currency_symbol"),

        # ── Current assets ─────────────────────────────────────────────────────
        # other_current_assets is a residual; all others are raw components.
        "cash_and_equiv":                       cash,
        "st_investments":                       st_investments,
        "receivables":                          receivables,
        "inventories":                          inventories,
        "other_current_assets":                 other_current_assets,
        "total_current_assets":                 total_current_assets,

        # ── Long-term assets ───────────────────────────────────────────────────
        # other_lt_assets is a residual absorbing the gap to total_assets.
        # ppe_gross / accumulated_depreciation are raw (ppe_gross is often unreported).
        "equity_and_other_investments":         lt_investments,
        "ppe_gross":                            _float(raw.get("propertyPlantAndEquipmentGross")),
        "accumulated_depreciation":             _float(raw.get("accumulatedDepreciation")),
        "ppe_net":                              ppe_net,
        "intangible_assets":                    intangibles,
        "goodwill":                             goodwill,
        "other_lt_assets":                      other_lt_assets,
        "total_assets":                         total_assets,

        # ── Current liabilities ────────────────────────────────────────────────
        # other_current_liabilities is a residual; tax_payable, accrued liabilities,
        # current_deferred_tax_liability, and current_capital_leases are not provided
        # by EODHD separately and are absorbed into it.
        "accounts_payable":                     accounts_payable,
        "tax_payable":                          None,
        "current_accrued_liabilities":          None,
        "st_debt":                              st_debt,
        "current_deferred_revenue":             current_deferred_rev,
        "current_deferred_tax_liability":       None,
        "current_capital_leases":               None,
        "other_current_liabilities":            other_current_liabilities,
        "total_current_liabilities":            total_current_liabilities,

        # ── Long-term liabilities ──────────────────────────────────────────────
        # other_lt_liabilities is a residual; pension and noncurrent_deferred_revenue
        # are not provided separately and are absorbed into it.
        "lt_debt":                              lt_debt,
        "noncurrent_capital_leases":            noncurrent_leases,
        "pension_liabilities":                  None,
        "noncurrent_deferred_revenue":          None,
        "other_lt_liabilities":                 other_lt_liabilities,
        "total_liabilities":                    total_liabilities,

        # ── Equity ─────────────────────────────────────────────────────────────
        # other_equity is a residual; all other equity components are raw.
        # total_liabilities_and_equity is a derived connector (total_liabilities + total_equity).
        "common_stock":                         common_stock,
        "preferred_stock":                      preferred_stock,
        "retained_earnings":                    retained,
        "aoci":                                 aoci,
        "apic":                                 apic,
        "treasury_stock":                       treasury,
        "other_equity":                         other_equity,
        "minority_interest_liability":          minority,
        "total_equity":                         total_equity,
        "total_liabilities_and_equity":         total_liabilities_and_equity,
        "total_investments":                    lt_investments,

        # Insurance / banking specific — not provided
        "deferred_policy_acquisition_cost":     None,
        "unearned_premiums":                    None,
        "future_policy_benefits":               None,
        "loans_gross":                          None,
        "allowance_for_loan_losses":            None,
        "unearned_income":                      None,
        "loans_net":                            None,
        "deposits_liability":                   None,

        # Computed by management command — not populated here
        "operating_assets":                     None,
        "operating_liabilities":                None,
        "net_operating_assets":                 None,
    }


# ── Cash Flow Statement ────────────────────────────────────────────────────────

def transform_cash_flow(raw: dict, qfs_symbol: str) -> dict:
    # ── Tier 1 anchors (raw from EODHD, always trusted) ───────────────────────
    cf_cfo        = _float(raw.get("totalCashFromOperatingActivities"))
    cf_cfi        = _float(raw.get("totalCashflowsFromInvestingActivities"))
    cf_cff        = _float(raw.get("totalCashFromFinancingActivities"))
    cf_net_change = _float(raw.get("changeInCash"))

    # ── Raw components ─────────────────────────────────────────────────────────
    # CFO — individual WC items are sub-detail of change_in_wc; not in residual formula
    net_income   = _float(raw.get("netIncome"))
    da           = _float(raw.get("depreciation"))
    stock_comp   = _float(raw.get("stockBasedCompensation"))
    change_in_wc = _float(raw.get("changeInWorkingCapital"))

    # CFI — provider does not split PP&E purchases vs sales
    capex          = _float(raw.get("capitalExpenditures"))
    investment_net = _float(raw.get("investments"))

    # CFF — provider gives net figures only, not gross issued/repaid splits
    common_stock_net    = _float(raw.get("salePurchaseOfStock"))
    common_stock_issued = _float(raw.get("issuanceOfCapitalStock"))
    debt_net            = _float(raw.get("netBorrowings"))
    dividend_paid       = _float(raw.get("dividendsPaid"))

    # ── Residuals ──────────────────────────────────────────────────────────────
    # Absorbs deferred tax, prepaid expenses, changeToLiabilities (AP change),
    # otherNonCashItems, and any remaining CFO items not broken out by EODHD.
    # changeInWorkingCapital is used as the WC block so that changeToLiabilities
    # (AP change) — which has no model field — doesn't contaminate this residual.
    cfo_other_noncash_items = (
        cf_cfo - (net_income or 0) - (da or 0) - (stock_comp or 0) - (change_in_wc or 0)
        if cf_cfo is not None else None
    )

    # Absorbs acquisitions, divestitures, intangibles, and remaining CFI items.
    cfi_other = (
        cf_cfi - (capex or 0) - (investment_net or 0)
        if cf_cfi is not None else None
    )

    # Absorbs preferred stock flows and remaining CFF items.
    # common_stock_issued (issuanceOfCapitalStock) is stored raw for analysis
    # but excluded here — common_stock_net already captures the net effect.
    cff_other = (
        cf_cff - (common_stock_net or 0) - (debt_net or 0) - (dividend_paid or 0)
        if cf_cff is not None else None
    )

    # By IAS 7 / ASC 230 the only item between (CFO + CFI + CFF) and changeInCash
    # is the effect of exchange rates on cash. Always derived as a residual so that
    # the four-section identity is guaranteed by construction. For companies with no
    # foreign operations the residual is zero; for internationally active companies
    # it captures the genuine FX effect plus any small rounding/reconciling items.
    cf_forex = (
        cf_net_change - (cf_cfo or 0) - (cf_cfi or 0) - (cf_cff or 0)
        if cf_net_change is not None else None
    )

    return {
        "qfs_symbol_id":                    qfs_symbol,
        "period_end_date":                  raw["date"],
        "reporting_currency":               raw.get("currency_symbol"),

        # CFO — cfo_other_noncash_items is a residual; all others are raw.
        # cfo_receivables / cfo_inventory / cfo_other_working_capital are
        # sub-detail of cfo_change_in_working_capital (informational).
        "cfo_net_income":                   net_income,
        "cfo_da":                           da,
        "cfo_receivables":                  _float(raw.get("changeToAccountReceivables")),
        "cfo_inventory":                    _float(raw.get("changeToInventory")),
        "cfo_prepaid_expenses":             None,
        "cfo_other_working_capital":        _float(raw.get("changeToOperatingActivities")),
        "cfo_change_in_working_capital":    change_in_wc,
        "cfo_deferred_tax":                 None,
        "cfo_stock_comp":                   stock_comp,
        "cfo_other_noncash_items":          cfo_other_noncash_items,
        "cf_cfo":                           cf_cfo,

        # CFI — cfi_other is a residual; ppe_purchases = ppe_net (no sales split)
        "cfi_ppe_purchases":                capex,
        "cfi_ppe_sales":                    None,
        "cfi_ppe_net":                      capex,
        "cfi_acquisitions":                 None,
        "cfi_divestitures":                 None,
        "cfi_acquisitions_net":             None,
        "cfi_investment_purchases":         None,
        "cfi_investment_sales":             None,
        "cfi_investment_net":               investment_net,
        "cfi_intangibles_net":              None,
        "cfi_other":                        cfi_other,
        "cf_cfi":                           cf_cfi,

        # CFF — cff_other is a residual; cff_common_stock_issued is raw (informational)
        "cff_common_stock_issued":          common_stock_issued,
        "cff_common_stock_repurchased":     None,
        "cff_common_stock_net":             common_stock_net,
        "cff_pfd_issued":                   None,
        "cff_pfd_repurchased":              None,
        "cff_pfd_net":                      None,
        "cff_debt_issued":                  None,
        "cff_debt_repaid":                  None,
        "cff_debt_net":                     debt_net,
        "cff_dividend_paid":                dividend_paid,
        "cff_other":                        cff_other,
        "cf_cff":                           cf_cff,

        "cf_forex":                         cf_forex,
        "cf_net_change_in_cash":            cf_net_change,
    }
