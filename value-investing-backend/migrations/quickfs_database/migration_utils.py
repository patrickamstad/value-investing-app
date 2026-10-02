import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import os
import pandas as pd
import numpy as np
import psycopg2
import requests
from io import StringIO

EODHD_BASE_URL = "https://eodhd.com/api"

# Uniqueness constraints used for ON CONFLICT DO NOTHING across all pipeline scripts.
CONFLICT_COLUMNS = {
    "companies":      ["qfs_symbol"],
    "income_annual":  ["qfs_symbol_id", "period_end_date"],
    "income_quarter": ["qfs_symbol_id", "period_end_date"],
    "balance_annual": ["qfs_symbol_id", "period_end_date"],
    "balance_quarter":["qfs_symbol_id", "period_end_date"],
    "cf_annual":      ["qfs_symbol_id", "period_end_date"],
    "cf_quarter":     ["qfs_symbol_id", "period_end_date"],
}


def get_db_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        database=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        port=os.environ["DB_PORT"],
    )


def get_exchanges(api_token: str) -> list[dict]:
    """Fetch all exchanges EODHD supports."""
    resp = requests.get(
        f"{EODHD_BASE_URL}/exchanges-list/",
        params={"api_token": api_token, "fmt": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

#define fields for different financial statements
traded_companies_fields = ["symbol", "qfs_symbol", "exchange", "name", "company_type", "currency", "industry"] #these correspond to column names in .csv files from quick fs

# traded_companies_fields_testing = ["ticker", "qfs_symbol", "exchange", "name", "company_type", "currency", "industry"] #these correspond to column names in .csv files from quick fs

income_statement_fields = ["qfs_symbol", "period_end_date", "revenue", "cogs", "gross_profit", "sga", "rnd", "special_charges", "other_opex", "total_opex", "operating_income", "interest_income", "interest_expense", "net_interest_income_normal", "other_nonoperating_income", "pretax_income", "income_tax", "net_income_continuing", "net_income_discontinued", "income_allocated_to_minority_interest", "other_income_statement_items", "net_income", "preferred_dividends", "net_income_available_to_shareholders", "eps_basic", "eps_diluted", "shares_basic", "shares_diluted", "shares_eop", "shares_eop_change", "premiums_earned", "net_investment_income", "fees_and_other_income", "net_policyholder_claims_expense", "policy_acquisition_expense", "interest_expense_insurance", "total_interest_income", "total_interest_expense", "net_interest_income", "total_noninterest_revenue", "credit_losses_provision", "net_interest_income_after_credit_losses_provision", "total_noninterest_expense", "da_income_statement_supplemental" ]
balance_sheet_fields = ["qfs_symbol", "period_end_date", "cash_and_equiv", "st_investments", "receivables", "inventories", "other_current_assets", "total_current_assets", "equity_and_other_investments", "ppe_gross", "accumulated_depreciation", "ppe_net", "intangible_assets", "goodwill", "other_lt_assets", "total_assets", "accounts_payable", "tax_payable", "current_accrued_liabilities", "st_debt", "current_deferred_revenue", "current_deferred_tax_liability", "current_capital_leases", "other_current_liabilities", "total_current_liabilities", "lt_debt", "noncurrent_capital_leases", "pension_liabilities", "noncurrent_deferred_revenue", "other_lt_liabilities", "total_liabilities", "common_stock", "preferred_stock", "retained_earnings", "aoci", "apic", "treasury_stock", "other_equity", "minority_interest_liability", "total_equity", "total_liabilities_and_equity", "total_investments", "deferred_policy_acquisition_cost", "unearned_premiums", "future_policy_benefits", "loans_gross", "allowance_for_loan_losses", "unearned_income", "loans_net", "deposits_liability"]
cf_statement_fields = ["qfs_symbol", "period_end_date", "cfo_net_income", "cfo_da", "cfo_receivables", "cfo_inventory", "cfo_prepaid_expenses", "cfo_other_working_capital", "cfo_change_in_working_capital", "cfo_deferred_tax", "cfo_stock_comp", "cfo_other_noncash_items", "cf_cfo", "cfi_ppe_purchases", "cfi_ppe_sales", "cfi_ppe_net", "cfi_acquisitions", "cfi_divestitures", "cfi_acquisitions_net", "cfi_investment_purchases", "cfi_investment_sales", "cfi_investment_net", "cfi_intangibles_net", "cfi_other", "cf_cfi", "cff_common_stock_issued", "cff_common_stock_repurchased", "cff_common_stock_net", "cff_pfd_issued", "cff_pfd_repurchased", "cff_pfd_net", "cff_debt_issued", "cff_debt_repaid", "cff_debt_net", "cff_dividend_paid", "cff_other", "cf_cff", "cf_forex", "cf_net_change_in_cash"]
key_ratios_fields = ["qfs_symbol", "period_end_date", "market_cap", "period_end_price", "enterprise_value", "book_value", "tangible_book_value", "price_to_earnings", "price_to_book", "price_to_sales", "price_to_tangible_book", "price_to_fcf", "price_to_pretax_income", "enterprise_value_to_earnings", "enterprise_value_to_book", "enterprise_value_to_tangible_book", "enterprise_value_to_sales", "enterprise_value_to_fcf", "enterprise_value_to_pretax_income", "ebitda", "capex", "fcf", "earning_assets", "policy_revenue", "underwriting_profit", "dividends", "payout_ratio", "income_tax_rate", "net_debt", "gross_margin", "ebitda_margin", "operating_margin", "pretax_margin", "net_income_margin", "fcf_margin", "net_interest_margin", "underwriting_margin", "roe", "roa", "roic", "roic_legacy", "roce", "rotce", "roi", "debt_to_equity", "debt_to_assets", "equity_to_assets", "assets_to_equity", "current_ratio", "earning_assets_to_equity", "loans_to_deposits", "loan_loss_reserve_to_loans", "revenue_per_share", "ebitda_per_share", "operating_income_per_share", "pretax_income_per_share", "fcf_per_share", "book_value_per_share", "tangible_book_per_share", "premiums_per_share", "revenue_growth", "gross_profit_growth", "ebitda_growth", "operating_income_growth", "pretax_income_growth", "net_income_growth", "eps_diluted_growth", "shares_diluted_growth", "shares_eop_growth", "cash_and_equiv_growth", "ppe_growth", "total_assets_growth", "total_equity_growth", "cfo_growth", "capex_growth", "fcf_growth", "revenue_cagr_10", "eps_diluted_cagr_10", "total_assets_cagr_10", "total_equity_cagr_10", "cf_cfo_cagr_10", "fcf_cagr_10"]


def bulk_insert(cursor, df, table_name):
    """bul insert migration entries into table"""
    buffer = StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    columns = ', '.join(df.columns)
    copy_sql = f"""COPY {table_name} ({columns}) FROM STDIN WITH CSV"""
    
    cursor.copy_expert(copy_sql, buffer)

def transform_date_to_string(date):
    return date.strftime('%Y-%m-%d')

def transform_date(date):
    return date + "-01"

def create_temp_staging_table(conn, target_table, staging_table):
    """Create a temporary staging table with the same structure as the target table"""
    with conn.cursor() as cur:
        # cur.execute(f"""
        #     CREATE TEMP TABLE {staging_table} (LIKE {target_table} INCLUDING ALL)
        # """)
        #when creating the temporary table based on the main table, we include constraints (like unique qfs_symbol + period_end_date). Quickfs has some dirty data where it has duplicates of qfs_symbol + period_end_date. When staging the data we don't want to handle duplicates. We will handle these later when inserting into the main table
        cur.execute(f"""
            CREATE TEMP TABLE {staging_table} (LIKE {target_table} EXCLUDING CONSTRAINTS EXCLUDING DEFAULTS)
        """)
        # drop the id column
        cur.execute(f"ALTER TABLE {staging_table} DROP COLUMN id;")
        conn.commit()

            # Query to list columns
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (staging_table,))
        
        columns = cur.fetchall()

    print(f"\n✅ Created temp table '{staging_table}' with the following columns:")
    for name, dtype in columns:
        print(f"  - {name} ({dtype})")


def bulk_insert_staging(conn, df, staging_table):
    """Copy dataframe into staging table"""
    buffer = StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {staging_table} ({', '.join(df.columns)}) FROM STDIN WITH CSV",
            buffer
        )
    conn.commit()

def get_relevant_columns(conn, staging_table, exclude_columns=["id"]):
    with conn.cursor() as cur:
    # Query to list columns
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (staging_table,))
        
        columns = [row[0] for row in cur.fetchall() if row[0] not in exclude_columns]

    return columns


def insert_from_staging(conn, staging_table, target_table, conflict_columns, cols_inserted_rows='qfs_symbol_id'):
    """Move unique rows from staging to target table"""
    conflict_cols = ", ".join(conflict_columns)

    #get all columns that should get inserted
    columns = get_relevant_columns(conn, staging_table)

    # print('relevant fields when inserting from staging to main: ', ', '.join(relevant_fields))
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {target_table} ({', '.join(columns)}) SELECT {', '.join(columns)} FROM {staging_table}
            ON CONFLICT ({conflict_cols}) DO NOTHING
            RETURNING {cols_inserted_rows}
        """)
        inserted_rows = cur.fetchall()
    conn.commit()

    # Return all qfs symbols that were inserted
    return [row[0] for row in inserted_rows]

def perform_consistency_check(df_migrated, df_database, file_name):
    """
    Function that checks whether rows present in the dataframe that has been migrated are consistent with rows present in the database

    para df_migrated:
        - type: pandas dataframe
        - descn: .csv data that has been loaded into dataframe and migrated to database
    
    para df_database:
        - type: pandas dataframe
        - descn: data that has been migrated and extracted from database
    """
    #merge the two dataframes on all colums
    df_merged = pd.merge(df_migrated, df_database, on=list(df_migrated.columns), how='left', indicator='exists')

    #where exists is set to 'both' we write True, otherwise False
    df_merged['exists'] = np.where(df_merged.exists == 'both', True, False)

    #extract rows where exists == False; number of rows must correspond to df_database.shape[0] - df_migrated.shape[0]
    if df_merged[df_merged['exists'] == False].shape[0] != abs(df_database.shape[0] - df_migrated.shape[0]):
        raise Exception(f'Nr. of migrated rows: {df_migrated.shape[0]} is not the same as new rows in database: {df_database.shape[0] - df_merged[df_merged["exists"] == False].shape[0]}, for file: {file_name}')
    else:
        print(f'file {file_name} has passed the consistency check!')


def migrate_financial_statements_optimized(sqlalchemy_engine, quickfs_df, psycopg2_connection, relevant_fields, target_table, staging_table, file_name = "", duplicate_subset=['qfs_symbol_id','period_end_date'], rename_columns = {'qfs_symbol' : 'qfs_symbol_id'}, set_has_new_financials=False):
    """
    migrates financial data in a more memory efficient way
    """
    #extract relevant fields
    df_extracted = quickfs_df[relevant_fields] 

    #rename columns, because django adds an _id to foreign key columns
    df_extracted = df_extracted.rename(columns=rename_columns)

    #remove ttm row (not possible to store string in date column)
    df_extracted = df_extracted[df_extracted.period_end_date != 'TTM']

    #transform date column from quickfs format YYYY-MM to django compatible format YYYY-MM-DD
    df_extracted['period_end_date'] = df_extracted['period_end_date'].apply(transform_date)   

    #bulk insert into staging table
    bulk_insert_staging(psycopg2_connection, df_extracted, staging_table)

    # print(f'migration table {target_table}, file: {file_name.split("/")[-1]} started!')
    #move entries from staging table to main table. We return a list of qfs symbols for which rows have been inserted
    rows_inserted = insert_from_staging(psycopg2_connection, staging_table, target_table, duplicate_subset)
    # print(f'migration table {target_table}, file: {file_name.split("/")[-1]} finished!')

    #set flag to true for qfs symbols which have new rows. companies with has_new_financials=true will be considered in valuation script
    if set_has_new_financials:
        query = """
                UPDATE quickfs_dj_tradedcompanies
                SET has_new_financials = TRUE
                WHERE qfs_symbol = ANY(%s)
                """

        # Execute the query
        psycopg2_connection.cursor().execute(query, (rows_inserted,))

        # Commit the changes
        psycopg2_connection.commit()


    # Clear staging table for next chunk
    with psycopg2_connection.cursor() as cur:
        cur.execute(f"TRUNCATE {staging_table}")
        psycopg2_connection.commit()


def migrate_financial_statements(sqlalchemy_engine, quickfs_df, psycopg2_connection, relevant_fields, target_table, file_name = "", duplicate_subset=['qfs_symbol_id','period_end_date'], rename_columns = {'qfs_symbol' : 'qfs_symbol_id'}, set_has_new_financials=False):
    """
    para quickfs_df:
        - type: dataframe
        - descn: quick fs .csv file loaded into a dataframe, from which the income statement, balance sheet and cash flow statement (based on relevant_fields parameter) can be extracted

    para psycopg2_connection:
        - type: psycopg2 connection that allows to create a cursor (example: psycopg2.connect(host="localhost", database="value-investing-dev", user="postgres", password="v,1846PSVv,1846PSV"))
        - descn: psycopg2 connection needed to create cursor and excute query

    para relevant_fields:
        - type: list of strings
        - descn: list of strings, where each element corresponds to a column available in quickfs_df
    
    para target_table:
        - type: string
        - descn: table to which the data should be migrated. target_table corresponds to a model defined in django backend
    
    para duplicate_subset:
        - type: list of strings
        - descn: list of columns that should be used to identify duplicates between database and quickfs file
    
    para rename_columns:
        - type: dictionary
        - descn: dictionary that defines renaming of dataframe columns in order to map possible differences from quickfs_df to django models; example: {'symbol' : 'ticker_id'}
    
    para set_has_new_financials:
        - type: boolean
        - descn: if set to true, if new rows are loaded for that financial statement (balance sheet, income or cash flow), the flag has_new_financials on TradedCompany is set to true and therefore will be reconsidered in valuation calculations

    return:
        - type: dataframe
        - descn: dataframe of entries that were migrated are returned
    """
    #extract relevant fields
    df_extracted = quickfs_df[relevant_fields]

    #rename columns
    #df_extractwe ed.rename(columns=rename_columns, inplace=True)
    #I think we no longer need to rename columns
    df_extracted = df_extracted.rename(columns=rename_columns)

    #remove ttm row (not possible to store string in date column)
    df_extracted = df_extracted[df_extracted.period_end_date != 'TTM']

    #transform date column from quickfs format YYYY-MM to django compatible format YYYY-MM-DD
    df_extracted['period_end_date'] = df_extracted['period_end_date'].apply(transform_date)   

    #define select query to extract existing rows in database; only get columns which are needed for merge
    # !!! here we load complete sql table into memory --> inefficient
    query = f"SELECT {', '.join(duplicate_subset)} FROM public.{target_table}"

    #create a psycopg cursor to execute query
    cursor = psycopg2_connection.cursor()

    #execute query
    cursor.execute(query)

    #transform database query content into dataframe
    #df_database = pd.DataFrame(cursor.fetchall(), columns=list(df_extracted.columns))
    df_database = pd.DataFrame(cursor.fetchall(), columns=duplicate_subset)

    #transform period_end_date column extracted from database from datetime object to string (in order to detect duplicates)
    df_database['period_end_date'] = df_database['period_end_date'].apply(transform_date_to_string)

    #concat file + database dataframes and remove duplicates based on subset columns (subset columns will be used to identify a duplicate)
    #new_entries = pd.concat([df_database, df_extracted, df_database]).drop_duplicates(subset=duplicate_subset, keep=False)
    concat_result = df_extracted.merge(df_database[duplicate_subset], on=duplicate_subset, how="left", indicator=True) 
    concat_result = concat_result[concat_result["_merge"] == "left_only"].drop(columns=["_merge"])
    concat_result = concat_result.drop_duplicates(subset=duplicate_subset, keep='first')

    #if concat result is empty we can skip migration
    if concat_result.empty:
        print(f'No new entries for {target_table}. Skipping Migration.')
        return concat_result
    
    #set flag to true in order to reconsider in valuation script
    if set_has_new_financials:
        #extract tickers which have new financial data
        qfs_symbols = concat_result["qfs_symbol_id"].unique().tolist()

        query = """
                UPDATE quickfs_dj_tradedcompanies
                SET has_new_financials = TRUE
                WHERE qfs_symbol = ANY(%s)
                """

        # Execute the query
        cursor.execute(query, (qfs_symbols,))

        # Commit the changes
        psycopg2_connection.commit()


    #writes entries to database which are not duplicate
    # print(f'migration table {target_table}, file: {file_name.split("/")[-1]} started!')

    #migrate the data
    bulk_insert(cursor, concat_result, target_table)
    psycopg2_connection.commit()
    cursor.close()


    #result = new_entries.to_sql(target_table, con=sqlalchemy_engine, if_exists='append', index=False, chunksize=chunk_size, method=method)
    # print(f'migration table {target_table}, file: {file_name} end! Nr. rows migrated: {concat_result.shape[0]}')

    return concat_result


def migrate_traded_companies_optimized(sqlalchemy_engine, quickfs_df, psycopg2_connection, relevant_fields, target_table, staging_table, file_name="", duplicate_subset=['qfs_symbol'], rename_columns = {'symbol' : 'ticker'}):
    #extract data needed for TradedCompanies table
    df_traded_companies = quickfs_df[relevant_fields]

    #drop duplicates in traded companies dataframe based on ticker symbol
    df_traded_companies = df_traded_companies.drop_duplicates(subset='qfs_symbol', keep="first")

    #rename symbol column to ticker in order to match django model
    df_traded_companies.rename(columns=rename_columns, inplace=True)

    #bulk insert into staging table
    bulk_insert_staging(psycopg2_connection, df_traded_companies, staging_table)

    # print(f'migration table {target_table}, file: {file_name.split("/")[-1]} started!')
    #move entries from staging table to main table. We return a list of qfs symbols for which rows have been inserted
    rows_inserted = insert_from_staging(psycopg2_connection, staging_table, target_table, duplicate_subset, cols_inserted_rows='qfs_symbol')
    # print(f'migration table {target_table}, file: {file_name.split("/")[-1]} finished!')

    # print('rows inserted migrate_traded_companies_optimized: ' , rows_inserted)

    # Clear staging table for next chunk
    with psycopg2_connection.cursor() as cur:
        cur.execute(f"TRUNCATE {staging_table}")
        psycopg2_connection.commit()

def migrate_traded_companies(sqlalchemy_engine, quickfs_df, psycopg2_connection, relevant_fields, target_table, file_name="", duplicate_subset=['qfs_symbol'], rename_columns = {'symbol' : 'ticker'}):
    #extract data needed for TradedCompanies table
    df_traded_companies = quickfs_df[relevant_fields]

    #drop duplicates in traded companies dataframe based on ticker symbol
    df_traded_companies = df_traded_companies.drop_duplicates(subset='qfs_symbol', keep="first")

    #rename symbol column to ticker in order to match django model
    df_traded_companies.rename(columns=rename_columns, inplace=True)
    
    # create a new cursor
    cur = psycopg2_connection.cursor()

    #define select queryt to get current records
    query = f"SELECT {', '.join(duplicate_subset)} from public.{target_table}" 

    #execute query
    cur.execute(query)

    #transform database query to dataframe
    df_database = pd.DataFrame(cur.fetchall(), columns=duplicate_subset)

    #only keep records from .csv quick fs file that are already present
    #OLD CODE
    #concat_result = pd.concat([df_database, df_traded_companies, df_database]).drop_duplicates(subset=duplicate_subset, keep=False)
    concat_result = df_traded_companies.merge(df_database[duplicate_subset], on=duplicate_subset, how="left", indicator=True) 
    concat_result =  concat_result[concat_result["_merge"] == "left_only"].drop(columns=["_merge"])
    
    #close psycog connection
    #cur.close()

    #if concat result is empty we can skip migration
    if concat_result.empty:
        print(f'No new entries for {target_table}. Skipping Migration.')
        return concat_result

    print(f'migration {target_table}, file: {file_name} started!')

    bulk_insert(cur, concat_result, target_table)
    psycopg2_connection.commit()
    cur.close()
    print(f'migration {target_table}, file: {file_name} ended! Nr. rows migrated: {concat_result.shape[0]}')

    #close engine
    return concat_result
