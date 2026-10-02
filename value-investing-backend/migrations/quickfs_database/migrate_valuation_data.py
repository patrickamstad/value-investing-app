
import psycopg2, os
from datetime import datetime, date
from psycopg2.extras import execute_values
from dotenv import load_dotenv
load_dotenv()

def compute_epv(conn, qfs_symbol, nr_years_avg_rev=4, nr_years_avg_op_margin=4, wacc=0.1, tax_rate=0.3):
    """
    Compute EPV for a single symbol and update the valuation_data table.
    Returns epv_equity and epv_business.
    """
    

    query = """
    WITH params AS (
        SELECT
            %s::text AS qfs_symbol,
            %s::float AS tax_rate,
            %s::float AS wacc
    ),
    fx AS (
        -- Units of trading currency per 1 unit of reporting currency. Defaults to 1.0
        -- when the company reports in its trading currency (no FxRate row exists for
        -- a same-currency pair - see migrate_fx_rates.py) or reporting_currency is not
        -- yet populated for this company.
        SELECT COALESCE(
            (SELECT fr.rate
             FROM quickfs_dj_incomestatementannual isa
             JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = isa.qfs_symbol_id
             JOIN quickfs_dj_fxrate fr ON fr.from_currency = isa.reporting_currency AND fr.to_currency = tc.currency
             WHERE isa.qfs_symbol_id = (SELECT qfs_symbol FROM params)
             ORDER BY isa.period_end_date DESC
             LIMIT 1),
            1.0
        ) AS rate
    ),
    avg_vals AS (
        SELECT
            (SELECT AVG(revenue) * (SELECT rate FROM fx)
             FROM (
                 SELECT revenue
                 FROM quickfs_dj_incomestatementannual, params
                 WHERE qfs_symbol_id = params.qfs_symbol
                 ORDER BY period_end_date DESC
                 LIMIT %s
             ) t) AS avg_revenue,
            (SELECT AVG(operating_income / NULLIF(revenue, 0))
             FROM (
                 SELECT revenue, operating_income
                 FROM quickfs_dj_incomestatementannual, params
                 WHERE qfs_symbol_id = params.qfs_symbol
                 ORDER BY period_end_date DESC
                 LIMIT %s
             ) t) AS avg_op_margin
    ),
    calc_epv AS (
        SELECT (avg_revenue * avg_op_margin) AS sustainable_ebit
        FROM avg_vals
    ),
    cash_debt AS (
        SELECT
            (cash_and_equiv + st_investments) * (SELECT rate FROM fx) AS cash,
            (st_debt + lt_debt) * (SELECT rate FROM fx) AS debt
        FROM quickfs_dj_balancesheetquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
          AND (qfs_symbol_id, period_end_date) IN (
              SELECT qfs_symbol_id, MAX(period_end_date)
              FROM quickfs_dj_balancesheetquarter, params
              WHERE qfs_symbol_id = params.qfs_symbol
              GROUP BY qfs_symbol_id
          )
    ),
    shares AS (
        SELECT shares_diluted
        FROM quickfs_dj_incomestatementquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
          AND period_end_date = (
              SELECT MAX(period_end_date)
              FROM quickfs_dj_incomestatementquarter, params
              WHERE qfs_symbol_id = params.qfs_symbol
          )
    )
    SELECT
    CASE
        WHEN (SELECT shares_diluted FROM shares) > 0 THEN
                COALESCE((
                ((SELECT sustainable_ebit FROM calc_epv) * (1 - (SELECT tax_rate FROM params))) / (SELECT wacc FROM params)
                + (SELECT cash FROM cash_debt) - (SELECT debt FROM cash_debt)
            ) / (SELECT shares_diluted FROM shares), -1)
        ELSE -1
    END AS epv_equity,
    COALESCE(
    ((SELECT sustainable_ebit FROM calc_epv) * (1 - (SELECT tax_rate FROM params))) / (SELECT wacc FROM params)
    + (SELECT cash FROM cash_debt) - (SELECT debt FROM cash_debt), -1) AS epv_business;
    """
    

    with conn.cursor() as cur:
        cur.execute(query, (qfs_symbol, tax_rate, wacc, nr_years_avg_rev, nr_years_avg_op_margin))
        result = cur.fetchone()
        conn.commit()
        return result if result is not None else (-1, -1)


def compute_epv_ttm(conn, qfs_symbol, wacc=0.1, tax_rate=0.3):
    query = """
    WITH params AS (
        SELECT
            %s::text AS qfs_symbol,
            %s::float AS tax_rate,
            %s::float AS wacc
    ),
    fx AS (
        SELECT COALESCE(
            (SELECT fr.rate
             FROM quickfs_dj_incomestatementquarter isq
             JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = isq.qfs_symbol_id
             JOIN quickfs_dj_fxrate fr ON fr.from_currency = isq.reporting_currency AND fr.to_currency = tc.currency
             WHERE isq.qfs_symbol_id = (SELECT qfs_symbol FROM params)
             ORDER BY isq.period_end_date DESC
             LIMIT 1),
            1.0
        ) AS rate
    ),
    last_four_quarters AS (
        SELECT revenue, operating_income
        FROM quickfs_dj_incomestatementquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
        ORDER BY period_end_date DESC
        LIMIT 4
    ),
    op_margin_data AS (
        SELECT
            COALESCE(SUM(operating_income) / NULLIF(SUM(revenue), 0), 0) AS avg_op_margin,
            COALESCE(SUM(revenue), 0) * (SELECT rate FROM fx) AS revenue_ttm
        FROM last_four_quarters
    ),
    cash_debt AS (
        SELECT
            COALESCE(cash_and_equiv + st_investments, 0) * (SELECT rate FROM fx) AS cash_and_equiv,
            COALESCE(st_debt + lt_debt, 0) * (SELECT rate FROM fx) AS debt
        FROM quickfs_dj_balancesheetquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
          AND (qfs_symbol_id, period_end_date) IN (
              SELECT qfs_symbol_id, MAX(period_end_date)
              FROM quickfs_dj_balancesheetquarter, params
              WHERE qfs_symbol_id = params.qfs_symbol
              GROUP BY qfs_symbol_id
          )
    ),
    shares_data AS (
        SELECT 
            COALESCE(shares_diluted, 0) AS shares_diluted
        FROM quickfs_dj_incomestatementquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
          AND period_end_date = (
              SELECT MAX(period_end_date)
              FROM quickfs_dj_incomestatementquarter, params
              WHERE qfs_symbol_id = params.qfs_symbol
          )
    )
    SELECT
    CASE
        WHEN (SELECT shares_diluted FROM shares_data) > 0 THEN
            COALESCE((
                ((SELECT revenue_ttm * avg_op_margin FROM op_margin_data) * (1 - (SELECT tax_rate FROM params))) / (SELECT wacc FROM params)
                + (SELECT cash_and_equiv FROM cash_debt) - (SELECT debt FROM cash_debt)
            ) / (SELECT shares_diluted FROM shares_data), -1)
        ELSE -1
    END AS epv_equity,
    COALESCE(
        ((SELECT revenue_ttm * avg_op_margin FROM op_margin_data) * (1 - (SELECT tax_rate FROM params))) / (SELECT wacc FROM params)
        + (SELECT cash_and_equiv FROM cash_debt) - (SELECT debt FROM cash_debt), -1
    ) AS epv_business
    FROM op_margin_data, cash_debt, shares_data;
    """
    with conn.cursor() as cur:
        cur.execute(query, (qfs_symbol, tax_rate, wacc))
        result = cur.fetchone()
        conn.commit()
        return result if result is not None else (-1, -1)

def equity_val_penman(conn, qfs_symbol, nr_years_avg_rev=3, nr_years_avg_op_margin=3, wacc=0.1, tax_rate=0.3):
    """
    Computes the equity value of a company according to Stephan Penman's book
    Returns equity_val_per_share, equity_val_total, implied_growth, rnoa.
    """

    # this query computes the equity value, implied growth and return on net operating assets
    # for computing the average net operating assets we retrieve net operating assets at FQ-4, FQ-8 and compute average (FQ-4 means 4 quarter backwards from current point in time). Also extract current book value b0
    query = """
    WITH params AS (
        SELECT
            %s::text AS qfs_symbol,
            %s::float AS tax_rate,
            %s::float AS wacc
    ),
    fx AS (
        SELECT COALESCE(
            (SELECT fr.rate
             FROM quickfs_dj_balancesheetquarter bsq
             JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = bsq.qfs_symbol_id
             JOIN quickfs_dj_fxrate fr ON fr.from_currency = bsq.reporting_currency AND fr.to_currency = tc.currency
             WHERE bsq.qfs_symbol_id = (SELECT qfs_symbol FROM params)
             ORDER BY bsq.period_end_date DESC
             LIMIT 1),
            1.0
        ) AS rate
    ),
    avg_vals AS (
        SELECT
            (SELECT AVG(revenue) * (SELECT rate FROM fx)
             FROM (
                 SELECT revenue
                 FROM quickfs_dj_incomestatementannual, params
                 WHERE qfs_symbol_id = params.qfs_symbol
                 ORDER BY period_end_date DESC
                 LIMIT %s
             ) t) AS avg_revenue,
            (SELECT AVG(operating_income / NULLIF(revenue, 0))
             FROM (
                 SELECT revenue, operating_income
                 FROM quickfs_dj_incomestatementannual, params
                 WHERE qfs_symbol_id = params.qfs_symbol
                 ORDER BY period_end_date DESC
                 LIMIT %s
             ) t) AS avg_op_margin
    ),
    calc_vals AS (
        SELECT
            (avg_revenue * avg_op_margin) AS sustainable_ebit
        FROM avg_vals
    ),
    noa_b0 AS (
        WITH ranked AS (
            SELECT net_operating_assets, total_equity,
                   ROW_NUMBER() OVER (ORDER BY period_end_date DESC) AS rn
            FROM quickfs_dj_balancesheetquarter, params
            WHERE qfs_symbol_id = params.qfs_symbol
        )
        SELECT
            AVG(CASE WHEN rn IN (4,8) THEN net_operating_assets END) * (SELECT rate FROM fx) AS avg_noa,
            MAX(CASE WHEN rn = 1 THEN total_equity END) * (SELECT rate FROM fx) AS b0
        FROM ranked
    ),
    shares AS (
        SELECT shares_diluted
        FROM quickfs_dj_incomestatementquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
          AND period_end_date = (
              SELECT MAX(period_end_date)
              FROM quickfs_dj_incomestatementquarter, params
              WHERE qfs_symbol_id = params.qfs_symbol
          )
    ),
    market_cap AS (
        SELECT tc.last_close_price * isq.shares_diluted AS market_cap
        FROM quickfs_dj_tradedcompanies tc
        JOIN (
            SELECT qfs_symbol_id, shares_diluted
            FROM quickfs_dj_incomestatementquarter
            WHERE qfs_symbol_id = (SELECT qfs_symbol FROM params)
            ORDER BY period_end_date DESC
            LIMIT 1
        ) isq ON tc.qfs_symbol = isq.qfs_symbol_id
        WHERE tc.qfs_symbol = (SELECT qfs_symbol FROM params)
          AND tc.last_close_price IS NOT NULL
    ),
    equity_calc AS (
        SELECT
            b0
            + ((sustainable_ebit * (1 - tax_rate) - wacc * avg_noa) / (1 + wacc))
            + ((sustainable_ebit * (1 - tax_rate) - wacc * avg_noa) / ((1 + wacc) * wacc))
            AS equity_val_total,
            sustainable_ebit * (1 - tax_rate) - wacc * avg_noa AS residual_earnings,
            sustainable_ebit * (1 - tax_rate) AS net_operating_profit,
            avg_noa, b0
        FROM calc_vals, noa_b0, params
    ),
    implied AS (
        SELECT 
            CASE 
                WHEN residual_earnings > 0 
                     AND ((residual_earnings / ((1+wacc) * (mc.market_cap - b0) - net_operating_profit + wacc * avg_noa))) < 0
                THEN -0.01
                ELSE wacc - (residual_earnings / ((1+wacc) * (mc.market_cap - b0) - net_operating_profit + wacc * avg_noa))
            END AS implied_growth
        FROM equity_calc, market_cap mc, params
    ),
    rnoa AS (
        SELECT CASE WHEN avg_noa > 0 THEN net_operating_profit / avg_noa ELSE NULL END AS rnoa
        FROM equity_calc
    )
    SELECT
        CASE 
            WHEN (SELECT shares_diluted FROM shares) > 0
            THEN equity_val_total / (SELECT shares_diluted FROM shares)
            ELSE -1
        END AS equity_val_per_share,
        ec.equity_val_total,
        i.implied_growth,
        r.rnoa
    FROM equity_calc ec
    CROSS JOIN rnoa r
    LEFT JOIN implied i ON true;
    """
    with conn.cursor() as cur:
        cur.execute(query, (qfs_symbol, tax_rate, wacc, nr_years_avg_rev, nr_years_avg_op_margin))
        result = cur.fetchone()
        conn.commit()

         # if equity val could not be computed we return dummy values
        if result is None:
            return (-1, -1, 1000, 0)
        else:
            return result


def equity_val_penman_ttm(conn, qfs_symbol, nr_years_avg_rev=3, nr_years_avg_op_margin=3, wacc=0.1, tax_rate=0.3):
    """
    Compute equity value according to penman (based on sustainable ebit of TTM)
    """
    query = """
    WITH params AS (
        SELECT
            %s::text AS qfs_symbol,
            %s::float AS tax_rate,
            %s::float AS wacc
    ),
    fx AS (
        SELECT COALESCE(
            (SELECT fr.rate
             FROM quickfs_dj_balancesheetquarter bsq
             JOIN quickfs_dj_tradedcompanies tc ON tc.qfs_symbol = bsq.qfs_symbol_id
             JOIN quickfs_dj_fxrate fr ON fr.from_currency = bsq.reporting_currency AND fr.to_currency = tc.currency
             WHERE bsq.qfs_symbol_id = (SELECT qfs_symbol FROM params)
             ORDER BY bsq.period_end_date DESC
             LIMIT 1),
            1.0
        ) AS rate
    ),
    calc_vals AS (
        -- SUM(operating_income) is a raw absolute amount (unlike the annual version's
        -- avg_revenue * avg_op_margin), so it needs direct conversion here.
        SELECT
            SUM(operating_income) * (SELECT rate FROM fx) AS sustainable_ebit
        FROM (
            SELECT operating_income
            FROM quickfs_dj_incomestatementquarter, params
            WHERE qfs_symbol_id = params.qfs_symbol
            ORDER BY period_end_date DESC
            LIMIT 4
        ) t
    ),
    noa_b0 AS (
        WITH ranked AS (
            SELECT net_operating_assets, total_equity,
                   ROW_NUMBER() OVER (ORDER BY period_end_date DESC) AS rn
            FROM quickfs_dj_balancesheetquarter, params
            WHERE qfs_symbol_id = params.qfs_symbol
        )
        SELECT
            AVG(CASE WHEN rn IN (4,8) THEN net_operating_assets END) * (SELECT rate FROM fx) AS avg_noa,
            MAX(CASE WHEN rn = 1 THEN total_equity END) * (SELECT rate FROM fx) AS b0
        FROM ranked
    ),
    shares AS (
        SELECT shares_diluted
        FROM quickfs_dj_incomestatementquarter, params
        WHERE qfs_symbol_id = params.qfs_symbol
          AND period_end_date = (
              SELECT MAX(period_end_date)
              FROM quickfs_dj_incomestatementquarter, params
              WHERE qfs_symbol_id = params.qfs_symbol
          )
    ),
    market_cap AS (
        SELECT tc.last_close_price * isq.shares_diluted AS market_cap
        FROM quickfs_dj_tradedcompanies tc
        JOIN (
            SELECT qfs_symbol_id, shares_diluted
            FROM quickfs_dj_incomestatementquarter
            WHERE qfs_symbol_id = (SELECT qfs_symbol FROM params)
            ORDER BY period_end_date DESC
            LIMIT 1
        ) isq ON tc.qfs_symbol = isq.qfs_symbol_id
        WHERE tc.qfs_symbol = (SELECT qfs_symbol FROM params)
          AND tc.last_close_price IS NOT NULL
    ),
    equity_calc AS (
        SELECT
            b0
            + ((sustainable_ebit * (1 - tax_rate) - wacc * avg_noa) / (1 + wacc))
            + ((sustainable_ebit * (1 - tax_rate) - wacc * avg_noa) / ((1 + wacc) * wacc))
            AS equity_val_total,
            sustainable_ebit * (1 - tax_rate) - wacc * avg_noa AS residual_earnings,
            sustainable_ebit * (1 - tax_rate) AS net_operating_profit,
            avg_noa, b0
        FROM calc_vals, noa_b0, params
    ),
    implied AS (
        SELECT 
            CASE 
                WHEN residual_earnings > 0 
                     AND ((residual_earnings / ((1+wacc) * (mc.market_cap - b0) - net_operating_profit + wacc * avg_noa))) < 0
                THEN -0.01
                ELSE wacc - (residual_earnings / ((1+wacc) * (mc.market_cap - b0) - net_operating_profit + wacc * avg_noa))
            END AS implied_growth
        FROM equity_calc, market_cap mc, params
    ),
    rnoa AS (
        SELECT CASE WHEN avg_noa > 0 THEN net_operating_profit / avg_noa ELSE NULL END AS rnoa
        FROM equity_calc
    )
    SELECT
        CASE 
            WHEN (SELECT shares_diluted FROM shares) > 0
            THEN equity_val_total / (SELECT shares_diluted FROM shares)
            ELSE -1
        END AS equity_val_per_share,
        ec.equity_val_total,
        i.implied_growth,
        r.rnoa
    FROM equity_calc ec
    CROSS JOIN rnoa r
    LEFT JOIN implied i ON true;
    """
    with conn.cursor() as cur:
        cur.execute(query, (qfs_symbol, tax_rate, wacc))
        result = cur.fetchone()
        conn.commit()

        #print('')

        # if equity val could not be computed we return dummy values
        if result is None:
            return (-1, -1, 1000, 0)
        else:
            return result

def update_prices(conn, qfs_symbols, valuation_date):
    query = """
    UPDATE quickfs_dj_valuation v
    SET price = tc.last_close_price
    FROM quickfs_dj_tradedcompanies tc
    WHERE v.qfs_symbol_id = tc.qfs_symbol
        AND v.valuation_date = %s
        AND v.price IS NULL
        AND tc.qfs_symbol = ANY(%s);
    """
    with conn.cursor() as cur:
        # psycopg2 expects a tuple for parameters
        cur.execute(query, (valuation_date, qfs_symbols))
    
    conn.commit()

psy_connection = psycopg2.connect(host=os.environ['DB_HOST'], database=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD'], port=os.environ['DB_PORT'])

# Create a cursor and fetch all qfs_symbol values
with psy_connection:
    with psy_connection.cursor() as cur:
        cur.execute("SELECT qfs_symbol FROM quickfs_dj_tradedcompanies WHERE has_new_financials = true;")
        qfs_symbols = [row[0] for row in cur.fetchall()]

        #qfs_symbols = cur.fetchall()  # Returns a list of tuples

today = datetime.today().strftime('%Y-%m-%d')

#qfs_symbol = 'YRD:US'

# equity_val_per_share, equity_val_total, implied_growth, rnoa = equity_val_penman(psy_connection, qfs_symbol)
# equity_val_per_share_ttm, equity_val_total_ttm, implied_growth_ttm, rnoa_ttm = equity_val_penman_ttm(psy_connection, qfs_symbol)

# print(f'qfs_symbol: {qfs_symbol} this is equity val per share: {equity_val_per_share} and implied_growth: {implied_growth}, rnoa: {rnoa}')
# print(f'qfs_symbol: {qfs_symbol} this is equity val per share: {equity_val_per_share_ttm} and implied_growth: {implied_growth_ttm}, rnoa: {rnoa_ttm}')
valuation_data = []

#print('qfs_symbols: ', qfs_symbols)

print('START MIGRATE_VALUATION_DATA')

# Loop over all stocks
for qfs_symbol in qfs_symbols:
    #print('qfs_symbol: ', qfs_symbol)
    epv_equity, epv_business = compute_epv(psy_connection, qfs_symbol)
    epv_equity_ttm, epv_business_ttm = compute_epv_ttm(psy_connection, qfs_symbol)
    equity_val_per_share, equity_val_total, implied_growth, rnoa = equity_val_penman(psy_connection, qfs_symbol)
    equity_val_per_share_ttm, equity_val_total_ttm, implied_growth_ttm, rnoa_ttm = equity_val_penman_ttm(psy_connection, qfs_symbol)

    valuation_data.append(( 
        qfs_symbol,
        today,  # or the valuation_date you want
        epv_business,
        epv_equity,
        epv_business_ttm,
        epv_equity_ttm,
        equity_val_total,
        implied_growth,
        equity_val_per_share,
        equity_val_total_ttm,
        implied_growth_ttm,
        equity_val_per_share_ttm,
        rnoa,
        rnoa_ttm
    ))


insert_query = """
    INSERT INTO quickfs_dj_valuation (
        qfs_symbol_id,
        valuation_date,
        epv_business,
        epv_per_share,
        epv_business_ttm,
        epv_per_share_ttm,
        penman_equity,
        penman_g,
        penman_per_share,
        penman_equity_ttm,
        penman_g_ttm,
        penman_per_share_ttm,
        rnoa,
        rnoa_ttm
    )
    VALUES %s
"""
print('start insert query: ')

with psy_connection.cursor() as cur:
    execute_values(cur, insert_query, valuation_data)
    psy_connection.commit()

#update price in valuation model
print('start update prices')
update_prices(psy_connection, qfs_symbols, today)
#     print(f'qfs_symbol: {qfs_symbol} these are epv_equity: {epv_equity} and epv_business: {epv_business}')
#     print(f'qfs_symbol: {qfs_symbol} these are epv_equity ttm: {epv_equity} and epv_business ttm: {epv_business}')



