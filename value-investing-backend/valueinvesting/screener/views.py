from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from quickfs_dj.models import BalanceSheetAnnual, BalanceSheetQuarter, IncomeStatementAnnual, IncomeStatementQuarter, TradedCompanies, CashFlowStatementAnnual, CashFlowStatementQuarter, KeyRatiosAnnual, TradedCompanies, KeyRatiosQuarter, LatestIncomeStatementAnnual, LatestBalanceSheetQuarter, LatestKeyRatiosAnnual, LatestKeyRatiosQuarter, LatestCashFlowStatementAnnual, Valuation, ScreenerData, FxRate
from screener.models import CustomMetrics, FilterViews, ValuationModel
from .serializers import StockScreenerFiltersSerializer, CustomMetricsSerializer, FilterViewsSerializer,CharFieldFilterOptions, ValuationModelSerizalizer
from django.core.cache import cache
from django.db import connection, transaction
import yfinance as yf
from quickfs import QuickFS
from .helpers import transform_expression, BALANCE_SHEET_GROUPS
import uuid
import os
#import yahoo_fin.stock_info as si
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from io import BytesIO
from scipy.optimize import fsolve,brentq,bisect
import pandas as pd
from rest_framework import status
from django.db.models.functions import ExtractYear
# from module_name import some_fn
# from scipy.optimize import brentq
# from .module_name import extract_revenue, process_list, generate_data
#from .epv import compute_epv_cpp
# from .helpers import add
from django.db.models import Q
from django.db.models import F, FloatField, Case, When, Value, ExpressionWrapper, Min, Max, Avg,Sum
from django.db.models.functions import Coalesce
from collections import defaultdict, Counter
from typing import Literal
import time



CACHE_TTL = 86400 #24 hours = 86400 seconds

#FINAL QUERY
# SELECT i.period_end_date, b.period_end_date, kr_y.period_end_date, i.ticker_id, b.ticker_id, i.revenue, b.cash_and_equiv
# FROM quickfs_incomestatementannual AS i
# INNER JOIN quickfs_balancesheetquarter AS b
# on i.ticker_id = b.ticker_id
# INNER JOIN quickfs_keyratiosannual AS kr_y
# on i.ticker_id = kr_y.ticker_id
# --where i.period_end_date >= to_date('01.01.2022', 'dd.mm.yyyy')
# --and b.period_end_date >= to_date('01.06.2023', 'dd.mm.yyyy')
# where i.revenue < 100000s
# and b.cash_and_equiv < 100000
# and kr_y.gross_margin > 0.2
# and (i.ticker_id, i.period_end_date) in (select ticker_id, max(period_end_date) from quickfs_incomestatementannual group by ticker_id)
# and (b.ticker_id, b.period_end_date) in (select ticker_id, max(period_end_date) from quickfs_balancesheetquarter group by ticker_id)
# and (kr_y.ticker_id, kr_y.period_end_date) in (select ticker_id, max(period_end_date) from quickfs_keyratiosannual group by ticker_id);







# algorithm we try to implement
# 1) for balance sheet quantities we will take most up-to-date quarterly numbers
# 2) for income statement (in a first implementation) we will take most up-to-date annual numbers
# 3) for cash flow statements we will take most up-to-date annual numbers
# 4) for key ratios (in a first implementation) we will take most up-to-date annual nummbers


# Implementation steps
# 1) implement endpoints that exposes all available fields for the different tables. response will have format: {incomeStatement: ["field1", "field2", "field3", "field4", "field5", etc.], balanceSheet: ["fieldb1", "fieldb2", etc.]}
# 2) it probably makes sense to define some mapping, but let's see


# select bs.period_end_date,bs.ticker_id, bs.cash_and_equiv, h.revenue from public.quickfs_balancesheetannual as bs inner join
# (select ticker_id, MAX(period_end_date) as MaxDateTime from public.quickfs_balancesheetannual group by ticker_id) bs_second
# on bs.ticker_id = bs_second.ticker_id
# and bs.period_end_date = bs_second.MaxDateTime
# --and bs.cash_and_equiv > 800000000000
# and bs.cash_and_equiv > 99000000000
# inner join
# --selection 
# (select ics.ticker_id, ics.revenue from public.quickfs_incomestatementannual as ics inner join
# (select ticker_id, MAX(period_end_date) as MaxDateTime from public.quickfs_incomestatementannual group by ticker_id) ics_second
#  on ics.ticker_id = ics_second.ticker_id
# and ics.period_end_date = ics_second.MaxDateTime
#  and ics.revenue > 10000000
# ) h
# on bs.ticker_id = h.ticker_id;

# Create your views here.


def cache_value(key, value = ''):
    """
    Function that caches the given value; if the value is already present it will just return the value
    """
    if cache.get(key) is None:
        cache.set(key, value)
        return value
    else:
        return cache.get(key)

# def create_joining_table_filter_query(table_name,base_table_alias, table_alias, filter_qtys):
#     """
#     This function will create the part of the query from line 10 to 16 or line 19 to 25
#     """
#     #create comma separated list of filter qtys in order to select them in sql query
#     selected_columns = ""

#     #store columns that will be filtered; these will later be used in line 1 of the complete query
#     filtered_columns = []


#     #create a filter string that contains all the AND conditions
#     filter_string = ""
#     for filter in filter_qtys:
#         #create selected columns string
#         selected_columns = selected_columns + f", table_alias.{filter['measure']}"

#         #append to filtered columns
#         filtered_columns.append(f"{table_alias}.{filter['measure']}")

#         #create filter condition
#         filter_condition = f"and table_alias.{filter['measure']} {filter['comparison']} {filter['qty']}"

#         #add filter condition to complete filter string
#         filter_string = filter_string + " " + filter_condition


#     #create final query
#     query = f"""
#             (select table_alias.ticker_id {selected_columns} from {table_name} as table_alias inner join
#             (select ticker_id, MAX(period_end_date) as MaxDateTime from {table_name} group by ticker_id) table_alias_second
#             on table_alias.ticker_id = table_alias.ticker_id
#             and table_alias.period_end_date = table_alias_second.MaxDateTime
#             {filter_string}
#             ) {table_alias}
#             on {base_table_alias}.ticker_id = {table_alias}.ticker_id
#             """
    
#     return query, filtered_columns

def create_first_line_of_query(base_table_alias, columns, count_rows=False):
    """
    this will create the first line of the query
    """
    #if counts rows is true we simply return select count(*)
    if count_rows:
        return "select count(*)"


    #we need to extract the primary key of the base table otherwise Django will throw an error
    if base_table_alias != 'comp':
        columns_list = f"select {base_table_alias}.id, {base_table_alias}.qfs_symbol_id, {base_table_alias}.period_end_date "
    else:
        columns_list = f"select {base_table_alias}.id, {base_table_alias}.ticker, {base_table_alias}.qfs_symbol as qfs_symbol_id "


    for column in columns:
        columns_list = columns_list + f",{column}"

    return columns_list

def create_filtered_columns(table_alias, filter_qtys):
    #store columns that will be filtered; these will later be used in line 1 of the complete query
    filtered_columns = []
    
    # #create filter conditions that will look like: and {table_alias}.some_filter_qty > 10000
    for filter in filter_qtys:
        #create filter condition of the format: and {table_alias}.some_filter_qty > 10000
        # filter_condition = f"and {table_alias}.{filter['measure']} {filter['comparison']} {filter['qty']}"

        #check if alias is defined for that measure
        if 'measure_alias' in filter:

            # check if table_alias is empty string (this is the case for derived quantities)
            if table_alias == "":
                #append to filtered columns
                # filtered_columns.append(f"{filter['measure']} as {filter['measure_alias']}")
                # filtered_columns.append(f"{filter['techName']} as {filter['measure_alias']}")
                filtered_columns.append(f"{filter['techName']} as \"{filter['measure_alias']}\"")

            else:
                #append to filtered columns
                # filtered_columns.append(f"{table_alias}.{filter['measure']} as {filter['measure_alias']}")
                # filtered_columns.append(f"{table_alias}.{filter['techName']} as {filter['measure_alias']}")
                filtered_columns.append(f"{table_alias}.{filter['techName']} as \"{filter['measure_alias']}\"")

        else:
              # check if table_alias is empty string (this is the case for derived quantities)
            if table_alias == "":
                # filtered_columns.append(f"{filter['measure']}")
                filtered_columns.append(f"{filter['techName']}")
            else:
                # filtered_columns.append(f"{table_alias}.{filter['measure']}")
                filtered_columns.append(f"{table_alias}.{filter['techName']}")




        #append to filtered columns
        # filtered_columns.append(f"{table_alias}.{filter['measure']}")

    return filtered_columns

def create_first_table_filter_query(table_name, table_alias):
    """
    This function will create the part of the query from line 2 to line 7 (see the following document for more details: https://docs.google.com/document/d/1kmnlVZLkyIG-QOl1kHjnjErNGSMKYis6_lwU0QrUNvQ/edit)
    """
    query = f"\n from {table_name} as {table_alias}"

    return query

    # return query, filtered_columns

def create_join_sql_statement(table_name, base_table_alias, table_alias):
    #check if table is quickfs_tradedcompanies; if it is quickfs then we need to join on ticker instead of ticker_id column
    # if table_alias != 'comp' and base_table_alias != 'comp':
    #     query = f"""\n inner join {table_name} as {table_alias}
    #         on {base_table_alias}.ticker_id = {table_alias}.ticker_id"""
    # elif base_table_alias == 'comp':
    #     query = f"""\n inner join {table_name} as {table_alias}
    #         on {base_table_alias}.ticker = {table_alias}.ticker_id"""
    # else:
    #     query = f"""\n inner join {table_name} as {table_alias}
    #         on {base_table_alias}.ticker_id = {table_alias}.ticker"""
        
    if table_alias != 'comp' and base_table_alias != 'comp':
        query = f"""\n inner join {table_name} as {table_alias}
            on {base_table_alias}.qfs_symbol_id = {table_alias}.qfs_symbol_id"""
    elif base_table_alias == 'comp':
        query = f"""\n inner join {table_name} as {table_alias}
            on {base_table_alias}.qfs_symbol = {table_alias}.qfs_symbol_id"""
    else:
        query = f"""\n inner join {table_name} as {table_alias}
            on {base_table_alias}.qfs_symbol_id = {table_alias}.qfs_symbol"""
    
    return query

    # return query, filtered_columns

def create_max_date_sql_statement(table_name, table_alias, min_date = '01.01.2022'):
    """
    
    para min_date:
        - type: string
        - descn: minimum date in order to filter companies that no longer exist; expected format is dd.mm.yyyy
    """
    #return f" and ({table_alias}.ticker_id, {table_alias}.period_end_date) in (select ticker_id, max(period_end_date) from {table_name} where period_end_date >= to_date('{min_date}', 'dd.mm.yyyy')  group by ticker_id)"
    return f" and ({table_alias}.qfs_symbol_id, {table_alias}.period_end_date) in (select qfs_symbol_id, max(period_end_date) from {table_name} where period_end_date >= to_date('{min_date}', 'dd.mm.yyyy')  group by qfs_symbol_id)"

def create_sql_filter_conditions(table_alias, filters, idx):
    final_filter_string = ""

    for inner_idx, filter in enumerate(filters):
        #in case it is is the first statement we will leave away the end
        if inner_idx == 0 and idx == 0:
            #check if table alias is empty
            if table_alias == "":
                final_filter_string += f" {filter['techName']} {filter['comparison']} {filter['qty']}"
            else:
                final_filter_string += f" {table_alias}.{filter['techName']} {filter['comparison']} {filter['qty']}"
        else:
            if table_alias == "":
                final_filter_string += f" and {filter['techName']} {filter['comparison']} {filter['qty']}"
            else:
                final_filter_string += f" and {table_alias}.{filter['techName']} {filter['comparison']} {filter['qty']}"

    return final_filter_string

# def get_table_name(type):
#     if type == 'kr_y':
#         return "quickfs_keyratiosannual"
#     elif type == 'kr_q':
#         return "quickfs_keyratiosquarter"
#     elif type == "income":
#         return "quickfs_incomestatementannual"
#     elif type == "balance":
#         return "quickfs_balancesheetquarter"
#     elif type == "cf":
#         return "quickfs_cashflowstatementannual"
#     elif type == "comp":
#         return "quickfs_tradedcompanies"


def get_django_model(type):
    # if type == 'kr_y':
    #     return KeyRatiosAnnual
    # elif type == 'kr_q':
    #     return KeyRatiosQuarter
    # elif type == "income":
    #     return IncomeStatementAnnual
    # elif type == "balance":
    #     return BalanceSheetQuarter
    # elif type == "cf":
    #     return CashFlowStatementAnnual
    # elif type == "comp":
    #     return TradedCompanies

    if type == 'kr_y':
        return LatestKeyRatiosAnnual
    elif type == 'kr_q':
        return LatestKeyRatiosQuarter
    elif type == "income":
        return LatestIncomeStatementAnnual
    elif type == "balance":
        return LatestBalanceSheetQuarter
    elif type == "cf":
        return LatestCashFlowStatementAnnual
    elif type == "comp":
        return TradedCompanies


def get_table_name_optimized(type):
    if type == 'kr_y':
        return "quickfs_dj_latestkeyratiosannual"
    elif type == 'kr_q':
        return "quickfs_dj_latestkeyratiosquarter"
    elif type == "income":
        return "quickfs_dj_latestincomestatementannual"
    elif type == "balance":
        return "quickfs_dj_latestbalancesheetquarter"
    elif type == "cf":
        return "quickfs_dj_latestcashflowstatementannual"
    elif type == "comp":
        return "quickfs_dj_tradedcompanies"

def get_table_name(type):
    if type == 'kr_y':
        return "quickfs_dj_keyratiosannual"
    elif type == 'kr_q':
        return "quickfs_dj_keyratiosquarter"
    elif type == "income":
        return "quickfs_dj_incomestatementannual"
    elif type == "balance":
        return "quickfs_dj_balancesheetquarter"
    elif type == "cf":
        return "quickfs_dj_cashflowstatementannual"
    elif type == "comp":
        return "quickfs_dj_tradedcompanies"
    

# def does_join_condition_exist(table_alias):
#     if table_alias == 'kr_q':
#         return len(key_ratios_q_filters) > 0
    
#this function is taken from the official django documentation: https://docs.djangoproject.com/en/3.2/topics/db/sql/#performing-raw-sql-queries
def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def create_filter_stocks_query_optimized(request, count_rows = False):
    #define base table alias
    base_table_alias = ""

    #define variable for filter statemetns
    filter_statements = ""

    #define variable to store inner join statements
    inner_joins = ""

    #define variable for max date statements
    max_date_statements = ""

    #store all columns that should get extracted in a list
    extracted_columns = []

    #prepare three lists to divide the different filter options
    income_statement_filters = []
    balance_sheet_filters = []
    cashflow_statement_filters = []
    key_ratios_q_filters = []
    key_ratios_y_filters = []
    traded_companies_filters = []
    derived_filters = [] #this includes filters of derived quantities like EV/EBIT. Note quantities like current_assets/current_liabilities are not considered derived as both measures

    def does_sql_already_exist(table_alias):
        """
        Function that checks whether a certain part of the query (for example inner join statement) is already present in the query or not. We define this as an inner function in order to have access to the different arrays key_ratios_q_filters, income_statement_filters, etc.
        """
        does_join_already_exist = False
        if table_alias == 'kr_q':
            does_join_already_exist =  len(key_ratios_q_filters) > 0
        elif table_alias == 'kr_y':
            does_join_already_exist =  len(key_ratios_y_filters) > 0
        elif table_alias == 'income':
            does_join_already_exist =  len(income_statement_filters) > 0
        elif table_alias == 'balance':
            does_join_already_exist =  len(balance_sheet_filters) > 0
        elif table_alias == 'cf':
            does_join_already_exist =  len(cashflow_statement_filters) > 0
        elif table_alias == 'comp':
            does_join_already_exist =  len(traded_companies_filters) > 0
        
        return does_join_already_exist

    #list that stores all filters
    allFilters = []

    for filter in request.data:
        if filter['table'] == 'kr_q': #kr_q stands for keyratios quarterly
            key_ratios_q_filters.append(filter)
        elif filter['table'] == 'kr_y': #kr_y stands for keyratios yearly
            key_ratios_y_filters.append(filter)
        elif filter['table'] == 'income': 
            income_statement_filters.append(filter)
        elif filter['table'] == 'balance':
            balance_sheet_filters.append(filter)
        elif filter['table'] == 'cf':
            cashflow_statement_filters.append(filter)
        elif filter['table'] == 'comp':
            traded_companies_filters.append(filter)
        elif type(filter['table']) == list:
            derived_filters.append(filter)

    #check for which tables filter exists
    if len(income_statement_filters) > 0:
        allFilters.append(income_statement_filters)

    if len(balance_sheet_filters) > 0:
        allFilters.append(balance_sheet_filters)

    if len(key_ratios_q_filters) > 0:
        allFilters.append(key_ratios_q_filters)

    if len(key_ratios_y_filters) > 0:
        allFilters.append(key_ratios_y_filters)

    if len(cashflow_statement_filters) > 0:
        allFilters.append(cashflow_statement_filters)

    if len(traded_companies_filters) > 0:
        allFilters.append(traded_companies_filters)

    if len(derived_filters) > 0:
        allFilters.append(derived_filters)

    for idx, filter in enumerate(allFilters):
        #extract type of filter statement (if filter statement for income statement, balance sheet, cashflow statement, keyratios or dervied quantity)
        measure_type = filter[0]['table']

        print(f'filter: {filter}, measure_type: {measure_type}')
        #check if type of filter condition is a list (if that is the case we are dealing with a derived quantitv, for example EV/EBIT)
        if type(measure_type) == list:
            # pass
            """
            what does change if we have a derived quantity like EV/EBIT?:
                - the 'type' property will be a list of the tables that are involed, like ['kr_q', 'income']
                - in case we have a derived quantity we need to make sure that join command and max_date sql statement for that table will be present (probably best to write a function if other types are present)
                - we also need to handle case where idx == 0
            """
            print('filter: inside list type ', filter)
            print('base_table_alias ', base_table_alias)

            for inner_idx, qty_type in enumerate(measure_type):
                #get the table name
                table_name = get_table_name_optimized(qty_type)

                #in case idx and inner_idx are zero we need to create line 2 part of query
                if idx == 0 and inner_idx == 0:
                    base_table_alias = qty_type

                    #create first part of sql query (line 2)
                    query_first_part = create_first_table_filter_query(table_name=table_name, table_alias=qty_type)

                    # check if other measure exists that uses the same table; in that case we do not need to add any join condition as this will be added later               
                    does_join_already_exist = does_sql_already_exist(qty_type)

                    if does_join_already_exist == False:
                        if measure_type != 'comp':
                            print(f'we create max_date query for {qty_type}')
                            #create max_date query for that table
                            max_date_query = create_max_date_sql_statement(table_name=table_name,table_alias=qty_type)

                            #add max date query to final max date statement
                            max_date_statements += max_date_query
                else:

                    # check if other measure exists that uses the same table; in that case we do not need to add any join condition as this will be added later                      
                    does_join_already_exist = does_sql_already_exist(qty_type)

                    print(f'we create join sql. table_name: {table_name}, base_table_alias: {base_table_alias}, table_alias: {qty_type}')
                    if does_join_already_exist == False:
                        query = create_join_sql_statement(table_name=table_name, base_table_alias=base_table_alias, table_alias=qty_type)

                        if measure_type != 'comp':
                            #create max_date query for that table
                            max_date_query = create_max_date_sql_statement(table_name=table_name,table_alias=qty_type)
                                
                            #add max date query to final max date statement
                            max_date_statements += max_date_query


                        #add inner join query to final inner join statement
                        inner_joins += query

            filtered_columns = create_filtered_columns(table_alias="", filter_qtys=filter)

            filter_condition = create_sql_filter_conditions(table_alias="", filters=filter, idx=idx)
        else:
        #get the table name
            table_name = get_table_name_optimized(measure_type)

            #in first iteration we will create line 2 of query (from some_table); otherwise we will create the join condition
            if idx == 0:
                base_table_alias = measure_type

                #create first part of sql query (line 2)
                query_first_part = create_first_table_filter_query(table_name=table_name, table_alias=measure_type)
                filtered_columns = create_filtered_columns(measure_type, filter)

            else:
                    # this will create join condition (line 3 & 4); inner join table_name as table_alias on base_table_alias.ticker_id = table_alias.ticker_id
                query = create_join_sql_statement(table_name=table_name, base_table_alias=base_table_alias, table_alias=measure_type)
                filtered_columns = create_filtered_columns(measure_type, filter)


                #add inner join query to final inner join statement
                inner_joins += query

            #create filter conditions for this table; these are of the form: table_alias.measure < 1000
            filter_condition = create_sql_filter_conditions(table_alias=measure_type, filters=filter, idx=idx)

            print('this is measure_type: ', measure_type)

            #quickfs_tradedcompanies does not have period end date, therefore we will skip function for that table
            if measure_type != 'comp':
                #create max_date query for that table
                max_date_query = create_max_date_sql_statement(table_name=table_name,table_alias=measure_type)
            
                #add max date query to final max date statement
                max_date_statements += max_date_query

        #add to final filter conditions
        filter_statements += filter_condition

        #add filtered columns to list of columns that will be extracted
        extracted_columns = extracted_columns + filtered_columns

    #create first line of query; as this endpoint is used for counting the number of stocks that are filtered, count_rows should always be set to True
    first_line = create_first_line_of_query(base_table_alias=base_table_alias, columns=extracted_columns, count_rows=count_rows)

    #construct the final query
    # final_query = f"{first_line} {query_first_part} {inner_joins} where {filter_statements} {max_date_statements};"
    final_query = f"{first_line} {query_first_part} {inner_joins} where {filter_statements};"

    return final_query


def create_filter_stocks_query(request, count_rows = False):
    #define base table alias
    base_table_alias = ""

    #define variable for filter statemetns
    filter_statements = ""

    #define variable to store inner join statements
    inner_joins = ""

    #define variable for max date statements
    max_date_statements = ""

    #store all columns that should get extracted in a list
    extracted_columns = []

    #prepare three lists to divide the different filter options
    income_statement_filters = []
    balance_sheet_filters = []
    cashflow_statement_filters = []
    key_ratios_q_filters = []
    key_ratios_y_filters = []
    traded_companies_filters = []
    derived_filters = [] #this includes filters of derived quantities like EV/EBIT. Note quantities like current_assets/current_liabilities are not considered derived as both measures

    def does_sql_already_exist(table_alias):
        """
        Function that checks whether a certain part of the query (for example inner join statement) is already present in the query or not. We define this as an inner function in order to have access to the different arrays key_ratios_q_filters, income_statement_filters, etc.
        """
        does_join_already_exist = False
        if table_alias == 'kr_q':
            does_join_already_exist =  len(key_ratios_q_filters) > 0
        elif table_alias == 'kr_y':
            does_join_already_exist =  len(key_ratios_y_filters) > 0
        elif table_alias == 'income':
            does_join_already_exist =  len(income_statement_filters) > 0
        elif table_alias == 'balance':
            does_join_already_exist =  len(balance_sheet_filters) > 0
        elif table_alias == 'cf':
            does_join_already_exist =  len(cashflow_statement_filters) > 0
        elif table_alias == 'comp':
            does_join_already_exist =  len(traded_companies_filters) > 0
        
        return does_join_already_exist

    #list that stores all filters
    allFilters = []

    for filter in request.data:
        if filter['table'] == 'kr_q': #kr_q stands for keyratios quarterly
            key_ratios_q_filters.append(filter)
        elif filter['table'] == 'kr_y': #kr_y stands for keyratios yearly
            key_ratios_y_filters.append(filter)
        elif filter['table'] == 'income': 
            income_statement_filters.append(filter)
        elif filter['table'] == 'balance':
            balance_sheet_filters.append(filter)
        elif filter['table'] == 'cf':
            cashflow_statement_filters.append(filter)
        elif filter['table'] == 'comp':
            traded_companies_filters.append(filter)
        elif type(filter['table']) == list:
            derived_filters.append(filter)

    #check for which tables filter exists
    if len(income_statement_filters) > 0:
        allFilters.append(income_statement_filters)

    if len(balance_sheet_filters) > 0:
        allFilters.append(balance_sheet_filters)

    if len(key_ratios_q_filters) > 0:
        allFilters.append(key_ratios_q_filters)

    if len(key_ratios_y_filters) > 0:
        allFilters.append(key_ratios_y_filters)

    if len(cashflow_statement_filters) > 0:
        allFilters.append(cashflow_statement_filters)

    if len(traded_companies_filters) > 0:
        allFilters.append(traded_companies_filters)

    if len(derived_filters) > 0:
        allFilters.append(derived_filters)

    for idx, filter in enumerate(allFilters):
        #extract type of filter statement (if filter statement for income statement, balance sheet, cashflow statement, keyratios or dervied quantity)
        measure_type = filter[0]['table']

        #check if type of filter condition is a list (if that is the case we are dealing with a derived quantitv, for example EV/EBIT)
        if type(measure_type) == list:
            # pass
            """
            what does change if we have a derived quantity like EV/EBIT?:
                - the 'type' property will be a list of the tables that are involed, like ['kr_q', 'income']
                - in case we have a derived quantity we need to make sure that join command and max_date sql statement for that table will be present (probably best to write a function if other types are present)
                - we also need to handle case where idx == 0
            """
            for inner_idx, qty_type in enumerate(measure_type):
                #get the table name
                table_name = get_table_name(qty_type)

                #in case idx and inner_idx are zero we need to create line 2 part of query
                if idx == 0 and inner_idx == 0:
                    base_table_alias = qty_type

                    #create first part of sql query (line 2)
                    query_first_part = create_first_table_filter_query(table_name=table_name, table_alias=qty_type)

                    # check if other measure exists that uses the same table; in that case we do not need to add any join condition as this will be added later               
                    does_join_already_exist = does_sql_already_exist(qty_type)

                    if does_join_already_exist == False:
                        if measure_type != 'comp':
                            print(f'we create max_date query for {qty_type}')
                            #create max_date query for that table
                            max_date_query = create_max_date_sql_statement(table_name=table_name,table_alias=qty_type)

                            #add max date query to final max date statement
                            max_date_statements += max_date_query
                else:
                    # check if other measure exists that uses the same table; in that case we do not need to add any join condition as this will be added later                      
                    does_join_already_exist = does_sql_already_exist(qty_type)

                    if does_join_already_exist == False:
                        query = create_join_sql_statement(table_name=table_name, base_table_alias=base_table_alias, table_alias=qty_type)

                        if measure_type != 'comp':
                            #create max_date query for that table
                            max_date_query = create_max_date_sql_statement(table_name=table_name,table_alias=qty_type)
                                
                            #add max date query to final max date statement
                            max_date_statements += max_date_query


                        #add inner join query to final inner join statement
                        inner_joins += query

            filtered_columns = create_filtered_columns(table_alias="", filter_qtys=filter)

            filter_condition = create_sql_filter_conditions(table_alias="", filters=filter, idx=idx)
        else:
        #get the table name
            table_name = get_table_name(measure_type)

            #in first iteration we will create line 2 of query (from some_table); otherwise we will create the join condition
            if idx == 0:
                base_table_alias = measure_type

                #create first part of sql query (line 2)
                query_first_part = create_first_table_filter_query(table_name=table_name, table_alias=measure_type)
                filtered_columns = create_filtered_columns(measure_type, filter)

            else:
                    # this will create join condition (line 3 & 4); inner join table_name as table_alias on base_table_alias.ticker_id = table_alias.ticker_id
                query = create_join_sql_statement(table_name=table_name, base_table_alias=base_table_alias, table_alias=measure_type)
                filtered_columns = create_filtered_columns(measure_type, filter)


                #add inner join query to final inner join statement
                inner_joins += query

            #create filter conditions for this table; these are of the form: table_alias.measure < 1000
            filter_condition = create_sql_filter_conditions(table_alias=measure_type, filters=filter, idx=idx)

            #quickfs_tradedcompanies does not have period end date, therefore we will skip function for that table
            if measure_type != 'comp':
                #create max_date query for that table
                max_date_query = create_max_date_sql_statement(table_name=table_name,table_alias=measure_type)

            
            #add max date query to final max date statement
            max_date_statements += max_date_query

        #add to final filter conditions
        filter_statements += filter_condition

        #add filtered columns to list of columns that will be extracted
        extracted_columns = extracted_columns + filtered_columns

    #create first line of query; as this endpoint is used for counting the number of stocks that are filtered, count_rows should always be set to True
    first_line = create_first_line_of_query(base_table_alias=base_table_alias, columns=extracted_columns, count_rows=count_rows)

    #construct the final query
    final_query = f"{first_line} {query_first_part} {inner_joins} where {filter_statements} {max_date_statements};"

    return final_query

class StocksFilterNumberOfStocksAPIView(APIView):
    """
    API endpoint that returns the current number of stocks which fulfil the current search criteria.
    The request is expecte in the following format:
    [
    {"techName" : "market_cap", "comparison" : ">", "qty" : 100000000, "table" : "kr_q"},
    {"techName" : "market_cap", "comparison" : ">", "qty" : 0, "table" : "kr_q"},
    {"techName" : "operating_income", "comparison" : ">", "qty" : 0, "table" : "income"},
    {"techName" : "enterprise_value", "comparison" : "<", "qty" : 0, "table" : "kr_q"},
    {"techName" : "industry", "comparison" : "not in", "qty" : "('Biotechnology', 'Asset Management','Insurance')", "table" : "comp"}
    ]

    property 'techName': corresponds to column name in corresponding table
    property 'comparison': defines operator that will be used for filtering (>, <, not in, =, etc.)
    property 'qty': numerical or string value that will be used for filtering (depends on the value type of the column, that is defined in measure)
    property 'type': defines the table in the which the column is defined. The following shortcuts are used for the different tables:
        - kr_q corresponds to keyratios quartely
        - kr_y corresponds to keyratios yearly
        - income corresponds to the income statement
        - balance corresponds to the quarterly/must up-to-date balance sheet data
        - cf corresponds to cash flow statement
        - comp corresponds to the traded companies table (this will mainly be used to filter out certain industries)
    """
    def post(self, request):
        final_query = create_filter_stocks_query(request, count_rows=True)

        with connection.cursor() as cursor:
            cursor.execute(final_query)
            # get a single line from the result
            row = cursor.fetchone()
            # get the value in the first column of the result (the only column)
            count_value = row[0]

        return Response({'nrOfStock' : count_value})


class StocksFilterQueryOptimizedAPIView(APIView):
    def initialize_request(self, request, *args, **kwargs):
        request = super().initialize_request(request, *args, **kwargs)
        # Modify the request data
        if request.method == 'POST':
            #check if data is an array
            if isinstance(request.data, list):
                #iterate through item and check if it is a custom metric
                for filter in request.data:
                    print('this is filter: ', filter)
                    #check if isCustomMetric is a key in the dictionary
                    if 'isCustomMetric' in filter:
                        if filter['isCustomMetric']:
                            # print('this is table property: ', filter['table'])
                            # if isinstance(filter['table'],list):
                            #     tables = filter['table']
                            # else:
                            #     tables=[]

                            #we need to transform the metric, to replace denominators with NULLIF(denominator, 0) to avoid zero division
                            newTechName = transform_expression(filter['techName'])
                            filter['techName'] = newTechName
                            filter['measure_alias'] = filter['readableName']

                            print('this is newTechName ', newTechName)

            # request.data._mutable = True  # Make data mutable
            # request.data['new_key'] = 'new_value'  # Add or modify data
            # request.data._mutable = False  # Make it immutable again (optional)
        return request


    def post(self, request):
        """
        Handles GET request to retrieve Gross Profit Margin = Gross Profit/Revenue
        Gross profit margin = Gross Proft/Total Revenue (page 33)
            - A durable competitive advantage can give freedom to price products freely
        and therefore leading to high gross profit margin.
            - Companies with durable competitive advantage have Gross Profit Margin > 40%
            - We are looking for consistency in high GPM, therefore consider last 10 years
            - It is important to note that a high GPM is not fail-safe as high operating expenses can eat up high GPM
        """
        #extract filters from request data
        filters = request.data

        #define table name
        table_name = "quickfs_dj_screenerdata"

        #default fields: these are fields that will be returned anyway like company name, industry, exchange, etc.
        default_fields = ["qfs_symbol_id", "name", "industry", "exchange"]

        #create a list for the selected fields and the where clause
        selected_fields = [] + default_fields
        where_conditions = []

        print('these are filters: ',filters)

        for item in filters:
            field = item['techName']
            readableName = item['readableName']

            #check that the readable name is valid (symbols like / - + are not valid)
            alias = re.sub(r'[^0-9a-zA-Z_]', '_', readableName)

            selected_fields.append(f"{field} as {alias}")
            comparison_operator = item['comparison'] #this is <, >, != etc.
            qty = item['qty']

            #add the where condition
            where_conditions.append(f"{field} {comparison_operator} {qty}")

        #combine all where clauses and create select fields
        where_clause = " AND ".join(where_conditions)
        select_clause = ", ".join(selected_fields)

        #create final query
        final_query = f"SELECT {select_clause} FROM {table_name} WHERE {where_clause}"

        print("final_query: ", final_query)

        with connection.cursor() as cursor:
            cursor.execute(final_query)
            #transform query result to dictionary
            query_result = dictfetchall(cursor)

        return Response({'queryResult' : query_result})


class StocksFilterQueryAPIView(APIView):
    def post(self, request):
        """
        Handles GET request to retrieve Gross Profit Margin = Gross Profit/Revenue
        Gross profit margin = Gross Proft/Total Revenue (page 33)
            - A durable competitive advantage can give freedom to price products freely
        and therefore leading to high gross profit margin.
            - Companies with durable competitive advantage have Gross Profit Margin > 40%
            - We are looking for consistency in high GPM, therefore consider last 10 years
            - It is important to note that a high GPM is not fail-safe as high operating expenses can eat up high GPM
        """
        final_query = create_filter_stocks_query(request, count_rows=False)

        print("final_query: ", final_query)

        with connection.cursor() as cursor:
            cursor.execute(final_query)
            #transform query result to dictionary
            query_result = dictfetchall(cursor)

        return Response({'queryResult' : query_result})


def get_ticker_price(ticker, qfs_symbol):
    current_price = 0
    price_currency = 'N/A'
    #extract implied shares from yahoo finance (Implied Shares Outstanding of common equity, assuming the conversion of all convertible subsidiary equity into common.)
    try:
        #create yahoo finance object
        company = yf.Ticker(ticker)

        #extract current price
        current_price = company.info["currentPrice"]

        #extract currency of yahoo finance price
        price_currency = company.info["currency"]
    except:
        #get traded company
        traded_company = TradedCompanies.objects.get(qfs_symbol=qfs_symbol)

        #if price data is not availabe on yahoo finance we will extract it from quickfs
        #intialize Client
        QUICKS_API_KEY = '0a78898493bf2325e59e01fb603023f9884d80c9' #os.environ["QUICKFS_API_KEY"]
        client = QuickFS(api_key=QUICKS_API_KEY)

        #get quickfs symbol (this is different from the ticker symbol. For example AAPL will be AAPL:US)
        quickfs_ticker = traded_company.qfs_symbol
        price_currency = traded_company.currency

        #extract price
        current_price = client.get_data_range(symbol = quickfs_ticker, metric="price")

    return current_price, price_currency


def get_nr_of_outstanding_shares(ticker, qfs_symbol):
    #get number of shares that are outstanding; we will get this from the most recent quarterly income statement
    income_statement_q = IncomeStatementQuarter.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')[0]
    nr_shares_qfs = income_statement_q.shares_diluted
    nr_shares = nr_shares_qfs

    #extract number of shares
    company = yf.Ticker(ticker)

    print('this is company yahoo finance: ', company)

    try:
        #extract number of implied shares
        nr_shares_yf = company.info["impliedSharesOutstanding"]

        print("after nr of shares yf")

        #we take the larger of the two (example is TSAT: number of implied shares is much higher than number of outstanding shares. Why? There are 13m tradable shares outstanding. Due to the merger with Loral and legacy Telesat, the controlling shareholders received units which are effectively shares in Telesat but they are not tradable until they are converted. So to calculate the economic market cap, you'd use the 50m shares. )
        if nr_shares_yf > nr_shares:
            nr_shares = nr_shares_yf
    except Exception as e:
        print('exception e: ', e)

    return nr_shares

def compute_epv(qfs_symbol, op_margin_nr_years = 5, avg_revenue_nr_years = 3, avg_da_nr_years = 5, trends_years = 7):
    """
    para op_margin_nr_years:
        - type: integer
        - descn: number of years that are used to compute the average operating margin
    
    para avg_revenue_nr_years:
        - type: integer
        - descn: number of years that are used to compute the average revenue; if set to 1, revenue of the most recent year will be taken

    para avg_da_nr_years:
        - type: integer
        - descn: number of years that are taken to compute the average D&A expenses and capital expenditures. Capital Expenditures includes PP&E and acquisitions

    para trends_years:
        - type: integer
        - descn: number of years that are taken to display trend graphs for revenue, operating margin, operating expenses and gross profit margin


    Function that computes the Earnings Power Value (EPV) of a company based on the procedure described by Bruce Greenwald. This involves the following steps:
        1. Compute the average operating margin based on the data of the past 5 years (if 5 years is not available takes as much data as possible)
        2. Compute sustainable EBIT, by multiplying the average operating margin by the average Revenue of the past 3 years
        3. Make Adjustments: Add D&A subtract maintenance capex add or remove any costs related to growth or extraordinary items (in this implementation we assume that D&A is a good measure for maintenance capex, therefore we do not make any adjustments)
        4. operating margin*average_revenue *(1-tax_rate) = sustainable NOPAT (Net Operating Profit after taxes)
        5. EPV Operating business = NOPAT/WACC
        6. EPV equity = EPV Operating Business + Cash - Debt
        7. EPV Equity per share = EPV Equity/nr_shares_outstanding
    """
    operating_margins = []
    operating_margins_trend = []
    operating_profits_ttm = []
    operating_margins_ttm = []
    revenues = []
    revenues_trend = []
    revenues_ttm = []
    gross_margin_trend = []
    total_opex= []
    da = [] #stores Depreciation & Amortization Expenses
    capex = [] #stores capital expenditures = PP&E + Acquisitions
    da_over_capex = [] #stores ratio of D&A/capex; if it is close to 1 it means that D&A is a good measure for maintenance capex; the further it is away from 1 (either smaller or larger) the less reliable is D&A as an estimate for maintenance capex
    tax_rate = 0.3
    wacc = 0.11
    

    #retrieve revenue data of the past 5 years
    income_statements = IncomeStatementAnnual.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date') #minus sign makes sure that ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01, ...

    #retrieve also quarterly income statement to compute TTM
    income_statements_q = IncomeStatementQuarter.objects.filter(qfs_symbol_id=qfs_symbol).order_by('-period_end_date')[:4]
    
    for income_q in income_statements_q:
        revenues_ttm.append(income_q.revenue)

        try:
            if income_q.operating_income is not None:
                operating_profits_ttm.append(income_q.operating_income)
        except TypeError:
            operating_profits_ttm.append(0)

        try:
            operating_margins_ttm.append(income_q.operating_income/income_q.revenue)
        except ZeroDivisionError:
            operating_margins_ttm.append(0)
        except TypeError:
            #operating_profits_ttm.append(0)
            operating_margins_ttm.append(0)
    
    for idx, income_statement in enumerate(income_statements):
        print('revenue.period_end_date: ', income_statement.period_end_date)
        if idx < trends_years:
            revenues_trend.append({'x': income_statement.period_end_date, 'y': income_statement.revenue})
            if income_statement.total_opex is None:
                total_opex.append({'x': income_statement.period_end_date, 'y': 0})
            else:
                total_opex.append({'x': income_statement.period_end_date, 'y': income_statement.total_opex})

            #gross profit margin
            try:
                gross_margin_trend.append({'x': income_statement.period_end_date, 'y':  income_statement.gross_profit/income_statement.revenue})
            except ZeroDivisionError:
                gross_margin_trend.append({'x': income_statement.period_end_date, 'y':0})
            except:
                gross_margin_trend.append({'x': income_statement.period_end_date, 'y':0})


            #compute operating margin
            try:
                operating_margins_trend.append({'x': income_statement.period_end_date, 'y':income_statement.operating_income/income_statement.revenue})
            except ZeroDivisionError:
                operating_margins_trend.append({'x': income_statement.period_end_date, 'y':0})
            except:
                operating_margins_trend.append({'x': income_statement.period_end_date, 'y':0})


        #check if idx is smaller than nr of years that should be used to compute the averge revenue
        if idx < avg_revenue_nr_years:
            revenues.append(income_statement.revenue)

        # check if idx is smaller that nr of years that should be used for average operating margin
        if idx < op_margin_nr_years:
            try:
                operating_margins.append(income_statement.operating_income/income_statement.revenue)
            except ZeroDivisionError:
                operating_margins.append(0)
            except TypeError:
                operating_margins.append(0)


    #retrieve cash flow statement data to extract D&A expenses and capital expenditures
    cfs_annual = CashFlowStatementAnnual.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')

    for idx, cfs in enumerate(cfs_annual):
        if idx < avg_da_nr_years:
            #append D&A value
            da.append(cfs.cfo_da)

            #take absolute value if cfi_ppe_purchases is negative (if negative it is an expense); if cfi_ppe_purchases it means the sold PP&E, then we set it to zero
            ppe = abs(cfs.cfi_ppe_purchases) if cfs.cfi_ppe_purchases < 0 else 0
            acquisitions = abs(cfs.cfi_acquisitions) if cfs.cfi_acquisitions < 0 else 0

            #append capex value
            capex.append(ppe + acquisitions)

            #compute D&A/capex ratio
            try:
                da_over_capex.append(cfs.cfo_da/(ppe+acquisitions))
            except ZeroDivisionError:
                da_over_capex.append(1)

    #step 1: compute the average operating margin
    avg_operating_margin = sum(operating_margins)/len(operating_margins)


    try:
        avg_operating_margin_ttm = sum(operating_profits_ttm)/sum(revenues_ttm) #sum(operating_margins_ttm)/len(operating_margins_ttm)
    except ZeroDivisionError:
        avg_operating_margin_ttm = 0
    
    #step 2: compute average revenue and multiply by average operating margin to obtain sustainable EBIT
    avg_revenue = sum(revenues)/len(revenues)
    # avg_revenue_ttm = sum(revenues_ttm)/len(revenues_ttm)

    sustainable_ebit = avg_operating_margin*avg_revenue
    sustainable_ebit_ttm = avg_operating_margin_ttm*sum(revenues_ttm)

    #step 3
    #TODO: currently we do not make any adjustments; we assume that D&A costs are a good approximation of the maintenance capex; in that case adjusted income is the same as sustainable ebit
    adjusted_income = sustainable_ebit
    adjusted_income_ttm = sustainable_ebit_ttm

    #compute NOPAT (Net Operating Profit After Taxes)
    nopat = adjusted_income*(1-tax_rate)
    nopat_ttm = adjusted_income_ttm*(1-tax_rate)

    #compute EPV operating business = nopat/wacc
    epv_op_busi = nopat/wacc
    evp_op_busi_ttm = nopat_ttm/wacc

    #compute EPV of Equity by adding cash and subtracting debt; we will take cash and debt values from the most recent quarterly balance sheet
    balance_sheet = BalanceSheetQuarter.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')[0]
    cash = balance_sheet.cash_and_equiv
    debt = balance_sheet.st_debt + balance_sheet.lt_debt

    #compute epv of equity
    epv_equity = epv_op_busi + cash - debt
    epv_equity_ttm = evp_op_busi_ttm + cash - debt

    #extract currency of company
    traded_company = TradedCompanies.objects.get(qfs_symbol=qfs_symbol)
    company_name = traded_company.name
    currency = traded_company.currency

    #get number of shares that are outstanding; we will get this from the most recent quarterly income statement
    nr_shares = get_nr_of_outstanding_shares(traded_company.ticker, qfs_symbol)

    #extract current share price for ticker symbol
    current_price, price_currency = get_ticker_price(traded_company.ticker, qfs_symbol)

    #compute epv equity per share
    try:
        epv_equity_per_share = epv_equity/nr_shares
        epv_equity_per_share_ttm = epv_equity_ttm/nr_shares
    except ZeroDivisionError:
        print('nr_shares is zero')
        epv_equity_per_share = None
        epv_equity_per_share_ttm = None

    #create response dictionary
    response = {'qfs_symbol' : qfs_symbol, 'name' : company_name, 'epv_per_share' : epv_equity_per_share, 'epv_per_share_ttm' :  epv_equity_per_share_ttm, 'epv_currency' : currency, 'current_price' : current_price, 'price_currency' : price_currency, 'avg_op_margin' : avg_operating_margin, 'avg_op_margin_ttm' : avg_operating_margin_ttm,  'avg_revenue' : avg_revenue, 'revenue_ttm' : sum(revenues_ttm), 'op_margins' : operating_margins, 'revenues' : revenues, 'da_over_capex' : da_over_capex, 'da' : da, 'capex' : capex, 'revenue_trend' : list(reversed(revenues_trend)) , 'gross_margin_trend' : list(reversed(gross_margin_trend)) , 'operating_margin_trend' : list(reversed(operating_margins_trend)) , 'total_opex_trend' : list(reversed(total_opex)), 'wacc' : wacc, 'tax_rate' : tax_rate, 'nr_of_shares' : nr_shares, 'epv_equity' : epv_equity, 'epv_equity_ttm' : epv_equity_ttm}

    return response



    # print('revenue: ', revenue)

class ComputeEPVAPIView(APIView):
    def post(self, request):
        """
        This endpoint will compute the EPV for the provided list of ticker symbols
        expected request format:
        request = {
                    tickers : ['AAPL', 'META']
                }
        """
        #tickers is of type list
        qfs_symbols = request.data['qfs_symbols']
        years_op_margin = request.data.get('years_op_margin', 5) #defines how many years into the past are taken to compute operating margin
        avg_revenue_nr_years = request.data.get('years_avg_revenue', 3) #defines how many years into the past are taken to compute operating margin

        #response list
        response = []

        for qfs_symbol in qfs_symbols:
            #check if value is in cache
            valuation = cache.get(f'{qfs_symbol}_EPV_{years_op_margin}_{avg_revenue_nr_years}')
            # valuation = None
            if valuation is None:
                #compute epv for ticker
                valuation = compute_epv(qfs_symbol, op_margin_nr_years=years_op_margin,  avg_revenue_nr_years = avg_revenue_nr_years)

                #store valuation in cache
                cache.set(f'{qfs_symbol}_EPV_{years_op_margin}_{avg_revenue_nr_years}', valuation, timeout=CACHE_TTL)
            response.append(valuation)

        return Response(response)


def get_revenue_ts(qfs_symbol, n=10):
    """
    returns revenue as a time series of the following format: [{'year' : '2021', 'value' : 20000}, {'year' : '2022, 'value' : 30000}, etc.]
    """
    last_records = (
    IncomeStatementAnnual.objects
    .filter(qfs_symbol_id=qfs_symbol)
    .annotate(year=ExtractYear('period_end_date'))  # get the year
    .order_by('-period_end_date')[:n]  # get last 5 years
    .values('year', 'revenue')
    )

    # Convert to desired format and sort by year ascending
    formatted_data = [
        {'year': str(record['year']), 'value': record['revenue']}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return formatted_data

def get_revenue(qfs_symbol):
    """
    Extracts min, max and avg revenue values of the past 5 years
    """
    # Get the most recent 5 records for this ticker, ordered by period_end_date descending
    last_5_records = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')
        .values('revenue')[:5]  # only retrieve revenue field
    )

    # Aggregate min, avg, max revenue on those 5 records
    revenue_stats = last_5_records.aggregate(
        min_revenue=Min('revenue'),
        avg_revenue=Avg('revenue'),
        max_revenue=Max('revenue')
    )

    return [
        revenue_stats['min_revenue'],
        revenue_stats['avg_revenue'],
        revenue_stats['max_revenue']
    ]

def get_nopat(qfs_symbol, n=5, tax_rate=0.3):
    """
    Function returns min, max and average nopat
    """
    incomes = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(
            nopat=ExpressionWrapper(
                F('operating_income') *(1-tax_rate),
                output_field=FloatField()
            )
        )
        .order_by('-period_end_date')  # ascending for correct RNOA calculation
        .only('period_end_date', 'operating_income')  # fetch only needed fields
    )[:n]


    # Aggregate min, avg, max revenue on those 5 records
    nopat_stats = incomes.aggregate(
        min_nopat=Min('nopat'),
        avg_nopat=Avg('nopat'),
        max_nopat=Max('nopat')
    )

    return [
        nopat_stats['min_nopat'],
        nopat_stats['avg_nopat'],
        nopat_stats['max_nopat']
    ]

def get_rnoa_cases(qfs_symbol, n=6, tax_rate = 0.3):
    """
    Computes RNOA_t = NOPAT_t/NOA_t-1 where NOPAT_t = EBIT_t*(1-tr) and NOA_t-1 = OperatingAssets_t-1 - operatingLiabilities_t-1
    Returns bear, base, bull RNOA. Bear is min(RNOA) over the last n-1 years; base is avg(RNOA) over the last n-1 years; bull is max(RNOA) over the last n-1 years
    """
    balances = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')  # descending to get latest n+1 periods
        .only('period_end_date', 'net_operating_assets')  # fetch only needed fields
    )[:n+1]

    # Step 2: fetch last n+1 income statements (only needed fields)
    incomes = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')  # ascending
        .only('period_end_date', 'operating_income')
    )[:n+1]

    print('qfs symbol: ', qfs_symbol)

    income_by_date = {inc.period_end_date: inc for inc in incomes}

    # step 3: compute rnoa. Remember we have ordered entries in descending order, so at position 0 we have the newest value
    rnoa_values = []
    for i in range(0, len(balances)-1):
        income_t = income_by_date.get(balances[i].period_end_date)
        if income_t is None:
            continue
        balance_t_1 = balances[i+1]

        print('income.operating_income: ', income_t.operating_income)
        print('income.net_operating_assets: ', balance_t_1.net_operating_assets)

        # avoid none or zero division
        if balance_t_1.net_operating_assets is None or balance_t_1.net_operating_assets == 0 or income_t.operating_income is None:
            continue

        rnoa = income_t.operating_income*(1-tax_rate)/balance_t_1.net_operating_assets
        rnoa_values.append(rnoa)

    # return bear, base and bull case
    return [
        round(min(rnoa_values),2) if rnoa_values else None,
        round((sum(rnoa_values)/len(rnoa_values)),2) if rnoa_values else None,
        round(max(rnoa_values),2) if rnoa_values else None,
    ]

def get_rnoa_ts(qfs_symbol, n = 10, tax_rate = 0.3, scaleFactor=100):
     # Step 1: fetch last n+1 balances with net_operating_assets
    balances = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')  # latest first
        .only('period_end_date', 'net_operating_assets')
    )[:n+1]


    # Step 2: fetch corresponding income statements
    incomes = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')  # latest first
        .only('period_end_date', 'operating_income')
    )[:n+1]

    incomes = sorted(incomes, key=lambda i: i.period_end_date)  # oldest -> newest
    balances = sorted(balances, key=lambda b: b.period_end_date)  # oldest -> newest

    # Build a date-keyed lookup so we match by period, not by position.
    # Balance sheet and income statement may have different row counts.
    income_by_date = {inc.period_end_date: inc for inc in incomes}

    # Step 3: compute RNOA using NOA from previous period
    rnoa_series = []
    for i in range(1, len(balances)):
        income_t = income_by_date.get(balances[i].period_end_date)
        if income_t is None:
            continue
        noa_prev = balances[i-1].net_operating_assets

        if noa_prev is None or noa_prev == 0 or income_t.operating_income is None:
            continue

        rnoa = income_t.operating_income * (1 - tax_rate) / noa_prev
        year = income_t.period_end_date.year
        rnoa_series.append({'year': str(year), 'value': rnoa*scaleFactor})

    # Step 4: keep only last n values
    rnoa_series = rnoa_series[-n:]

    return rnoa_series


def get_ato_ts(qfs_symbol, n = 10, tax_rate = 0.3, scaleFactor=1):
     # Step 1: fetch last n+1 balances with net_operating_assets
    balances = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')  # latest first
        .only('period_end_date', 'net_operating_assets')
    )[:n+1]


    # Step 2: fetch corresponding income statements
    incomes = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')  # latest first
        .only('period_end_date', 'revenue')
    )[:n+1]

    incomes = sorted(incomes, key=lambda i: i.period_end_date)  # oldest -> newest
    balances = sorted(balances, key=lambda b: b.period_end_date)  # oldest -> newest

    income_by_date = {inc.period_end_date: inc for inc in incomes}

    # Step 3: compute ATO using NOA from previous period
    ato_series = []
    for i in range(1, len(balances)):
        income_t = income_by_date.get(balances[i].period_end_date)
        if income_t is None:
            continue
        noa_prev = balances[i-1].net_operating_assets

        if noa_prev is None or noa_prev == 0 or income_t.revenue is None:
            continue

        ato = income_t.revenue / noa_prev
        year = income_t.period_end_date.year
        ato_series.append({'year': str(year), 'value': ato*scaleFactor})

    # Step 4: keep only last n values
    ato_series = ato_series[-n:]

    return ato_series

def get_noa(qfs_symbol, n=2):
    """
    Compute net operating assets = operating_assets - operating liabilities
    Return a list [bear, base, bull]. Each case is computed as the average noa over the past n years
    """ 
    #compute net operating assets
    balances = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')  # latest first
        .only('period_end_date', 'net_operating_assets')
    )[:n]

    # balances = (
    #     BalanceSheetAnnual.objects
    #     .filter(qfs_symbol_id=qfs_symbol)
    #     .annotate(
    #         noa=ExpressionWrapper(
    #             F('operating_assets') - F('operating_liabilities'),
    #             output_field=FloatField()
    #         )
    #     )
    #     .order_by('-period_end_date')  # ascending for correct RNOA calculation
    #     .only('period_end_date', 'operating_assets', 'operating_liabilities')  # fetch only needed fields
    # )[:n]

   # Compute average NOA
    average_noa = balances.aggregate(avg_noa=Avg('net_operating_assets'))['avg_noa']

    return [average_noa, average_noa, average_noa]


def get_noa_ts(qfs_symbol, n=10):
    last_records = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))  # get the year
        .order_by('-period_end_date')[:n]  # get last 5 years
        .values('year', 'net_operating_assets')
    )

    # Convert to desired format and sort by year ascending
    formatted_data = [
        {'year': str(record['year']), 'value': record['net_operating_assets']}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return formatted_data

def get_op_margin_ts(qfs_symbol, n=10, scaleFactor=100):
    """
    Returns operating margins as a time series of the following format:
    [{'year': '2021', 'value': 0.25}, {'year': '2022', 'value': 0.27}, ...]
    """

    # Query the most recent N records for this symbol
    last_records = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')[:n]
        .values('year', 'operating_income', 'revenue')
    )

    # Compute operating margin = operating_income / revenue
    formatted_data = []
    for record in last_records:
        revenue = record.get('revenue')
        op_income = record.get('operating_income')

        if revenue not in (None, 0):
            margin = op_income / revenue
            formatted_data.append({
                'year': str(record['year']),
                'value': round(margin * scaleFactor, 3)  # round to 3 decimals
            })

    # Sort by year ascending
    formatted_data.sort(key=lambda x: x['year'])

    return formatted_data

def get_gp_margin_ts(qfs_symbol, n=10, scaleFactor=100):
    """
    Returns gross profit margins as a time series of the following format:
    [{'year': '2021', 'value': 0.25}, {'year': '2022', 'value': 0.27}, ...]
    """

    # Query the most recent N records for this symbol
    last_records = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')[:n]
        .values('year', 'gross_profit', 'revenue')
    )

    # Compute operating margin = operating_income / revenue
    formatted_data = []
    for record in last_records:
        revenue = record.get('revenue')
        op_income = record.get('gross_profit')

        if revenue not in (None, 0):
            margin = op_income / revenue
            formatted_data.append({
                'year': str(record['year']),
                'value': round(margin*scaleFactor, 3)  # round to 3 decimals
            })

    # Sort by year ascending
    formatted_data.sort(key=lambda x: x['year'])

    return formatted_data


def get_rnoa(qfs_symbol, years: int = 5, include_ttm: bool = True, precision: int = 3, tax_rate: float = 0.3):
    """
    Computes RNOA_t = NOPAT_t/NOA_t-1 where NOPAT_t = EBIT_t*(1-tr) and NOA_t-1 = OperatingAssets_t-1 - operatingLiabilities_t-1
    Returns bear, base, bull RNOA. Bear is min(RNOA) over the last n-1 years; base is avg(RNOA) over the last n-1 years; bull is max(RNOA) over the last n-1 years
    """
    balances = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')  # descending to get latest n+1 periods
        .only('period_end_date', 'net_operating_assets')  # fetch only needed fields
    )[:years+1]

    # Step 2: fetch last n+1 income statements (only needed fields)
    incomes = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')  # ascending
        .only('period_end_date', 'operating_income')
    )[:years+1]

    rnoa = defaultdict()
    incomes = list(reversed(incomes))   # now ascending (oldest first)
    balances = list(reversed(balances))

    balance_by_date = {b.period_end_date: b for b in balances}
    balance_dates = sorted(balance_by_date.keys())

    # step 3: compute rnoa. Iterate over consecutive balance periods; look up income by date.
    for i in range(1, len(balance_dates)):
        income_t = next((inc for inc in incomes if inc.period_end_date == balance_dates[i]), None)
        if income_t is None:
            continue
        year_t = income_t.year
        op_income_t = income_t.operating_income
        noa_t_minus_1 = balance_by_date[balance_dates[i-1]].net_operating_assets

        # avoid invalid denominator
        if noa_t_minus_1 in (None, 0) or op_income_t is None:
            rnoa[year_t] = 0
            continue

        rnoa_value = op_income_t * (1 - tax_rate) / noa_t_minus_1
        rnoa[year_t] = round(rnoa_value, precision)

    if include_ttm:
        #get sum of operating income of the last four quarters
        res_op_income = (IncomeStatementQuarter.objects
                        .filter(qfs_symbol_id = qfs_symbol)
                        .order_by('-period_end_date')
                        .aggregate(
                            sum_op=Sum(Coalesce('operating_income', Value(0),output_field=FloatField())),
                        ))
        
        balance = (BalanceSheetQuarter.objects
                   .filter(qfs_symbol_id = qfs_symbol)
                   .order_by('-period_end_date')
                   .only('net_operating_assets'))[3]
        
       #keep only the forth quarter
        # balance = balance[-1] 
        
        # compute rnoa
        rnoa_ttm = (
            round(res_op_income['sum_op']*(1-tax_rate) / balance.net_operating_assets,precision)
            if balance.net_operating_assets else 0
        )

        rnoa["TTM"] = rnoa_ttm

    return rnoa
 

def get_asset_turnover(qfs_symbol, years: int = 5, include_ttm: bool = True, precision: int = 3, tax_rate: float = 0.3):
    """
    Computes Asset turnover which is defined as ATO = Revenue_t/NOA_t-1
    """
    balances = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')  # descending to get latest n+1 periods
        .only('period_end_date', 'net_operating_assets')  # fetch only needed fields
    )[:years+1]

    # Step 2: fetch last n+1 income statements (only needed fields)
    incomes = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')  # ascending
        .only('period_end_date', 'revenue')
    )[:years+1]

    ato = defaultdict()
    incomes = list(reversed(incomes))
    balances = list(reversed(balances))


    # step 3: compute ato. Remember we have ordered entries in descending order, so at position 0 we have the newest value
    for i in range(1, len(incomes)):
        year_t = incomes[i].year
        revenue_t = incomes[i].revenue
        noa_t_minus_1 = balances[i-1].net_operating_assets

        # avoid invalid denominator
        if noa_t_minus_1 in (None, 0) or revenue_t is None:
            ato[year_t] = 0
            continue

        ato_value = revenue_t / noa_t_minus_1
        ato[year_t] = round(ato_value, precision)

    if include_ttm:
        #get sum of operating income of the last four quarters
        res_rev = (IncomeStatementQuarter.objects
                        .filter(qfs_symbol_id = qfs_symbol)
                        .order_by('-period_end_date')
                        .aggregate(
                            sum_rev=Sum(Coalesce('revenue', Value(0),output_field=FloatField())),
                        ))
        
        balance = (BalanceSheetQuarter.objects
                   .filter(qfs_symbol_id = qfs_symbol)
                   .order_by('-period_end_date')
                   .only('net_operating_assets'))[3]
        
       #keep only the forth quarter
        # balance = balance[-1] 
        
        # compute rnoa
        ato_ttm = (
            round(res_rev['sum_rev'] / balance.net_operating_assets,precision)
            if balance.net_operating_assets else 0
        )

        ato["TTM"] = ato_ttm

    return ato

def get_op_margins(qfs_symbol, years: int = 5, include_ttm: bool = True, precision: int = 3):
    """
    Extracts min, max and avg revenue values of the past 5 years
    """
    # Get the most recent 5 records for this ticker, ordered by period_end_date descending
    # Fetch only the fields we actually need
    last_n_records = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')
        .values('year','period_end_date', 'operating_income', 'revenue')[:years]
    )

    margins = defaultdict()

    for i, stmt in enumerate(reversed(last_n_records)):
        margins[stmt.get('year', 0)] = round(stmt['operating_income']/stmt['revenue'],precision) if stmt['revenue'] not in (None, 0) else 0


    #include ttm values
    if include_ttm:
        res = (
            IncomeStatementQuarter.objects
            .filter(qfs_symbol__qfs_symbol=qfs_symbol)
            .order_by('-period_end_date')[:4]
            .aggregate(
                sum_rev=Sum(Coalesce('revenue', Value(0),output_field=FloatField())),
                sum_op=Sum(Coalesce('operating_income', Value(0),output_field=FloatField())),
            )
        )

        op_margin_ttm = (
            round(res['sum_op'] / res['sum_rev'],precision)
            if res['sum_rev'] else None
        )

        margins["TTM"] = op_margin_ttm


    return margins


def get_gp_margins(qfs_symbol, years: int = 5, include_ttm: bool = True, precision: int = 3):
    """
    Extracts gross profit margin for the past n years
    """
    # Get the most recent 5 records for this ticker, ordered by period_end_date descending
    # Fetch only the fields we actually need
    last_n_records = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))
        .order_by('-period_end_date')
        .values('year','period_end_date', 'gross_profit', 'revenue')[:years]
    )

    margins = defaultdict()

    for i, stmt in enumerate(reversed(last_n_records)):
        margins[stmt.get('year', 0)] = round(stmt['gross_profit']/stmt['revenue'],precision) if stmt['revenue'] not in (None, 0) else 0


    #include ttm values
    if include_ttm:
        res = (
            IncomeStatementQuarter.objects
            .filter(qfs_symbol__qfs_symbol=qfs_symbol)
            .order_by('-period_end_date')[:4]
            .aggregate(
                sum_rev=Sum(Coalesce('revenue', Value(0),output_field=FloatField())),
                sum_gp=Sum(Coalesce('gross_profit', Value(0),output_field=FloatField())),
            )
        )

        gp_margin_ttm = (
            round(res['sum_gp'] / res['sum_rev'],precision)
            if res['sum_rev'] else None
        )

        margins["TTM"] = gp_margin_ttm


    return margins



def get_effective_tax_rates(qfs_symbol, years: int=5, include_ttm: bool = True, precision: int = 3):
    """
    computes the effective tax rate as income_tax/pretax_income
    """
    ins = (IncomeStatementAnnual.objects
           .filter(qfs_symbol_id=qfs_symbol)
           .annotate(year=ExtractYear('period_end_date'))
           .order_by('-period_end_date')[:years]
           .values('year', 'pretax_income', 'income_tax')
    )

    effective_tr = defaultdict()

    #compute effective tax rate
    for i, stmt in enumerate(reversed(ins)):
        effective_tr[stmt.get('year', 0)] = round(stmt['income_tax']/stmt['pretax_income'],precision) if stmt['pretax_income'] not in (None, 0) and stmt['income_tax'] is not None else 0

    #compute ttm
    #include ttm values
    if include_ttm:
        res = (
            IncomeStatementQuarter.objects
            .filter(qfs_symbol__qfs_symbol=qfs_symbol)
            .order_by('-period_end_date')[:4]
            .aggregate(
                sum_itax=Sum(Coalesce('income_tax', Value(0),output_field=FloatField())),
                sum_income=Sum(Coalesce('pretax_income', Value(0),output_field=FloatField())),
            )
        )

        eff_tr_ttm = (
            round(res['sum_itax'] / res['sum_income'], precision)
            if res['sum_income'] else None
        )

        effective_tr["TTM"] = eff_tr_ttm

    return effective_tr

def get_op_margin(qfs_symbol):
    """
    Extracts min, max and avg revenue values of the past 5 years
    """
    # Get the most recent 5 records for this ticker, ordered by period_end_date descending
    # Fetch only the fields we actually need
    last_5_records = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .order_by('-period_end_date')
        .values('operating_income', 'revenue')[:5]
    )

    # Compute the operating margins (safely handle division by zero)
    margins = [
        record['operating_income'] / record['revenue']
        for record in last_5_records
        if record['revenue'] not in (None, 0)
    ]

    if not margins:  # No valid margins (e.g., missing or zero revenues)
        return [None, None, None]

    # Compute min, average, max manually in Python
    min_margin = min(margins)
    avg_margin = sum(margins) / len(margins)
    max_margin = max(margins)

    return [round(min_margin,2), round(avg_margin,2), round(max_margin,2)]

def get_cash_ts(qfs_symbol, n=10):
    last_records = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'), total_cash = F('cash_and_equiv') + F('st_investments'))  # get the year
        .order_by('-period_end_date')[:n]  # get last 5 years
        .values('year', 'total_cash')
    )

    # Convert to desired format and sort by year ascending
    formatted_data = [
        {'year': str(record['year']), 'value': record['total_cash']}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return formatted_data

def get_cash(qfs_symbol):
    # Get the latest record for the given ticker
    latest_record = BalanceSheetQuarter.objects.filter(
        qfs_symbol_id=qfs_symbol
    ).order_by('-period_end_date').first()

    if latest_record:
        total_cash = latest_record.cash_and_equiv + latest_record.st_investments
    else:
        total_cash = None

    return total_cash

def get_book_value(qfs_symbol):
    # Get the latest record for the given ticker
    latest_record = BalanceSheetQuarter.objects.filter(
        qfs_symbol_id=qfs_symbol
    ).order_by('-period_end_date').first()

    if latest_record:
        total_equity = latest_record.total_equity
    else:
        total_equity = None

    return total_equity

def get_book_value_ts(qfs_symbol, n=10):
    last_records = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'))  # get the year
        .order_by('-period_end_date')[:n]  # get last 5 years
        .values('year', 'total_equity')
    )

    # Convert to desired format and sort by year ascending
    formatted_data = [
        {'year': str(record['year']), 'value': record['total_equity']}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return formatted_data

def get_debt_ts(qfs_symbol, n=10, fx_rate: float = 1.0):
    last_records = (
        BalanceSheetAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .annotate(year=ExtractYear('period_end_date'), total_debt = F('st_debt') + F('lt_debt'))  # get the year
        .order_by('-period_end_date')[:n]  # get last 5 years
        .values('year', 'total_debt')
    )

    # Convert to desired format and sort by year ascending
    formatted_data = [
        {'year': str(record['year']), 'value': record['total_debt'] * fx_rate if record['total_debt'] is not None else None}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return formatted_data

def get_debt(qfs_symbol):
    # Get the latest record for the given ticker
    latest_record = BalanceSheetQuarter.objects.filter(
        qfs_symbol_id=qfs_symbol
    ).order_by('-period_end_date').first()

    if latest_record:
        total_debt = latest_record.st_debt + latest_record.lt_debt
    else:
        total_debt = None

    return total_debt


def get_nr_diluted_shares_ts(qfs_symbol, n=10):
    """
    returns revenue as a time series of the following format: [{'year' : '2021', 'value' : 20000}, {'year' : '2022, 'value' : 30000}, etc.]
    """
    last_records = (
    IncomeStatementAnnual.objects
    .filter(qfs_symbol_id=qfs_symbol)
    .annotate(year=ExtractYear('period_end_date'))  # get the year
    .order_by('-period_end_date')[:n]  # get last 5 years
    .values('year', 'shares_diluted')
    )

    # Convert to desired format and sort by year ascending
    formatted_data = [
        {'year': str(record['year']), 'value': record['shares_diluted']}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return formatted_data

def get_detected_currencies(qfs_symbol: str) -> tuple:
    """
    Returns (detected_reporting_currency, detected_trading_currency) - the raw,
    un-overridden values straight from the DB. reporting_currency comes from this
    company's latest fundamentals row; trading_currency from TradedCompanies.currency.

    Kept separate from any session override (see PenmanValuationAPIView/computeAssetVal)
    so the frontend can always show "detected: X -> overridden: Y" and revert back to
    the true detected value, even after multiple overrides in the same session.
    """
    latest = (
        IncomeStatementAnnual.objects
        .filter(qfs_symbol_id=qfs_symbol)
        .exclude(reporting_currency__isnull=True)
        .order_by('-period_end_date')
        .first()
    )
    reporting_currency = latest.reporting_currency if latest else None
    trading_currency = TradedCompanies.objects.filter(qfs_symbol=qfs_symbol).first().currency
    return reporting_currency, trading_currency


def get_fx_rate(reporting_currency: str, trading_currency: str) -> float:
    """
    Units of trading_currency per 1 unit of reporting_currency. Both currencies must
    already be resolved (auto-detected or overridden - that's the caller's job via
    get_detected_currencies + any override). Upstream provider data can be wrong or
    inconsistent across periods (seen in practice: EODHD mistagging a company's most
    recent filing's currency), which is exactly what an override corrects for.

    Defaults to 1.0 when reporting/trading currency already match, either is unknown,
    or no FxRate row exists for the pair - mirrors the same fallback used in
    migrations/quickfs_database/migrate_valuation_data.py's fx CTE.
    """
    if not reporting_currency or not trading_currency or reporting_currency == trading_currency:
        return 1.0

    fx = FxRate.objects.filter(from_currency=reporting_currency, to_currency=trading_currency).first()
    return fx.rate if fx else 1.0


def get_nr_diluted_shares(qfs_symbol):
    # Get the latest record for the given ticker
    latest_record = IncomeStatementQuarter.objects.filter(
        qfs_symbol_id=qfs_symbol
    ).order_by('-period_end_date').first()


    if latest_record:
        nr_shares_dil = latest_record.shares_diluted
    else:
        nr_shares_dil = None

    return nr_shares_dil


def get_financials(qfs_symbol: str, modelAnnual, modelQuarter, type: Literal["income", "balance"], years: int = 5, metric_fields: list[str] = ["revenue", "cogs", "gross_profit", "sga", "rnd", "other_opex", "operating_income", "income_tax"], include_ttm: bool = True, fx_rate: float = 1.0):
    """
    type: use to determine how ttm is computed. For income, last four entries of quarterly statements are summed up; for balance most recent entry is taken
    fx_rate: multiplier applied to every returned value - pass the company's reporting-currency
    -> trading-currency rate (see get_fx_rate) for monetary fields; leave at 1.0 for share counts.
    """
    
    # Fetch only needed fields + period_end_date
    qs = (modelAnnual.objects
            .filter(qfs_symbol_id=qfs_symbol)
            .annotate(year=ExtractYear('period_end_date'))
            .order_by('-period_end_date')[:years]
            .values('year','period_end_date', *metric_fields)
        )

    if not qs.exists():
        return {"symbol": qfs_symbol, "periods": [], "metrics": []}

    latest_statements = list(qs)

    # Build periods: FY-5 → FY-1 → TTM
    periods = []
    for i, stmt in enumerate(reversed(latest_statements)):
        periods.append(stmt.get("year", 0))
    
    # Compute TTM if requested
    ttm_values = {}
    if include_ttm and type == "income":
        # Fetch the latest 4 quarterly statements
        qtrs = modelQuarter.objects.filter(qfs_symbol__qfs_symbol=qfs_symbol)\
            .order_by('-period_end_date')[:4]\
            .values(*metric_fields)

        if qtrs.exists():
            # Sum each metric over the last 4 quarters
            for field in metric_fields:
                ttm_values[field] = sum(q.get(field, 0.0) or 0.0 for q in qtrs)

            periods.append("TTM")
            latest_statements.insert(0,ttm_values)  # append TTM as a pseudo-statement
    elif include_ttm and type == "balance":
         # Fetch the latest 4 quarterly statements
        qtrs = modelQuarter.objects.filter(qfs_symbol__qfs_symbol=qfs_symbol)\
            .order_by('-period_end_date')[:1]\
            .values(*metric_fields)

        if qtrs.exists():
            row = qtrs[0]  # extract the dict row

            # Sum each metric over the last 4 quarters
            for field in metric_fields:
                ttm_values[field] = row.get(field, 0.0)

            periods.append("TTM")
            latest_statements.insert(0,ttm_values)  # append TTM as a pseudo-statement

    # Build metrics dict
    metrics = defaultdict(dict)
    for period_label, stmt in zip(periods, reversed(latest_statements)):
        for field in metric_fields:
            metrics[field][period_label] = (stmt.get(field, 0.0) or 0.0) * fx_rate

    return {
        "symbol": qfs_symbol,
        "periods": periods,
        "metrics": metrics
    }

def get_financials_ts(qfs_symbol: str, model, metric: str, years: int = 10, scale_factor = 1, fx_rate: float = 1.0):
    """
    Function that returns time series for requested metric in the following format: [{'year': 2021, 'value' : 10000}, {'year': 2022, 'value' : 20000}, etc.]
    fx_rate: multiplier for reporting-currency -> trading-currency conversion (see get_fx_rate);
    leave at 1.0 for ratios/share counts.
    """
    last_records = (model.objects
                    .filter(qfs_symbol_id = qfs_symbol)
                    .annotate(year=ExtractYear('period_end_date'))
                    .order_by('-period_end_date')[:years]
                    .values('year', metric)
            )

    #we will sort data from oldest to newest (2019, 2020, 2021)
    ts = [
        {'year': str(record['year']), 'value': record[metric] * scale_factor * fx_rate if record[metric] is not None else None}
        for record in sorted(last_records, key=lambda x: x['year'])
    ]

    return ts


class PenmanValuationAPIView(APIView):
    def get(self, request, qfs_symbol):
        # return Response("ok")
        # Get number of years from query parameter (default to 5)
        years = int(request.query_params.get("years", 5))
        include_ttm = request.query_params.get("ttm", "true").lower() == "true"

        #get unix timestamp to store last fetch time
        last_fetch = int(time.time() * 1000) 

        nr_shares = get_nr_diluted_shares(qfs_symbol=qfs_symbol)

        # fx_rate converts this company's reporting-currency fundamentals into its
        # trading currency (= currency, matches last_close_price). Applied to every
        # monetary field below; never to share counts (nr_shares, shares_diluted,
        # nr_shares_ts) or ratios (margins, RNOA, ATO, effective tax rate), which are
        # currency-invariant by construction.
        # reportingCurrency/tradingCurrency query params let the frontend override
        # auto-detection for this request only - upstream provider data can be wrong
        # (reporting currency especially; trading currency far more rarely). detected_*
        # stays the raw DB value regardless, so the frontend can always show
        # "detected -> overridden" and revert back to it.
        reporting_currency_detected, currency_detected = get_detected_currencies(qfs_symbol)
        reporting_currency = request.query_params.get("reportingCurrency") or reporting_currency_detected
        currency = request.query_params.get("tradingCurrency") or currency_detected
        fx_rate = get_fx_rate(reporting_currency, currency)

        # get different income statement items
        revenue = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter,type = "income", years=years, metric_fields=["revenue"], fx_rate=fx_rate)
        cogs = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["cogs"], fx_rate=fx_rate)
        gp = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["gross_profit"], fx_rate=fx_rate)
        sga = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["sga"], fx_rate=fx_rate)
        rnd = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["rnd"], fx_rate=fx_rate)
        other_opex = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["other_opex"], fx_rate=fx_rate)
        operating_income = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["operating_income"], fx_rate=fx_rate)
        income_tax = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter, type = "income", years=years, metric_fields=["income_tax"], fx_rate=fx_rate)
        gp_margins = get_gp_margins(qfs_symbol, years)
        op_margins = get_op_margins(qfs_symbol, years)
        rnoa = get_rnoa(qfs_symbol, years)
        ato = get_asset_turnover(qfs_symbol, years)
        effective_tr = get_effective_tax_rates(qfs_symbol, years)

        #get operating assets, operating liabilities, net operating assets
        op_assets = get_financials(qfs_symbol, modelAnnual=BalanceSheetAnnual, modelQuarter=BalanceSheetQuarter,type = "balance", years=years, metric_fields=["operating_assets"], fx_rate=fx_rate)
        op_liab = get_financials(qfs_symbol, modelAnnual=BalanceSheetAnnual, modelQuarter=BalanceSheetQuarter,type = "balance", years=years, metric_fields=["operating_liabilities"], fx_rate=fx_rate)
        net_op_assets = get_financials(qfs_symbol, modelAnnual=BalanceSheetAnnual, modelQuarter=BalanceSheetQuarter,type = "balance", years=years, metric_fields=["net_operating_assets"], fx_rate=fx_rate)
        book_value = get_financials(qfs_symbol, modelAnnual=BalanceSheetAnnual, modelQuarter=BalanceSheetQuarter,type = "balance", years=years, metric_fields=["total_equity"], fx_rate=fx_rate)

        #get debt and number of shares
        st_debt = get_financials(qfs_symbol, modelAnnual=BalanceSheetAnnual, modelQuarter=BalanceSheetQuarter,type = "balance", years=years, metric_fields=["st_debt"], fx_rate=fx_rate)
        lt_debt = get_financials(qfs_symbol, modelAnnual=BalanceSheetAnnual, modelQuarter=BalanceSheetQuarter,type = "balance", years=years, metric_fields=["lt_debt"], fx_rate=fx_rate)
        shares_diluted = get_financials(qfs_symbol, modelAnnual=IncomeStatementAnnual, modelQuarter=IncomeStatementQuarter,type = "balance", years=years, metric_fields=["shares_diluted"])

        #sum the short-term and long-term debt
        debt = dict(Counter(st_debt['metrics']["st_debt"]) + Counter(lt_debt['metrics']["lt_debt"]))

        #extract time series data in format [{'year': 2021, 'value' : 10000}, {'year': 2022, 'value' : 20000}, etc.]
        revenue_ts = get_financials_ts(qfs_symbol, model=IncomeStatementAnnual, metric='revenue', fx_rate=fx_rate)
        cogs_ts = get_financials_ts(qfs_symbol, model=IncomeStatementAnnual, metric='cogs', fx_rate=fx_rate)
        sga_ts = get_financials_ts(qfs_symbol, model=IncomeStatementAnnual, metric='sga', fx_rate=fx_rate)
        rnd_ts = get_financials_ts(qfs_symbol, model=IncomeStatementAnnual, metric='rnd', fx_rate=fx_rate)
        other_opex_ts = get_financials_ts(qfs_symbol, model=IncomeStatementAnnual, metric='other_opex', fx_rate=fx_rate)
        op_margin_ts = get_op_margin_ts(qfs_symbol)
        gp_margin_ts = get_gp_margin_ts(qfs_symbol)
        op_income_ts = get_financials_ts(qfs_symbol, model=IncomeStatementAnnual, metric='operating_income', fx_rate=fx_rate)
        op_assets_ts = get_financials_ts(qfs_symbol, model=BalanceSheetAnnual, metric='operating_assets', fx_rate=fx_rate)
        op_liab_ts = get_financials_ts(qfs_symbol, model=BalanceSheetAnnual, metric='operating_liabilities', fx_rate=fx_rate)
        net_op_assets_ts = get_financials_ts(qfs_symbol, model=BalanceSheetAnnual, metric='net_operating_assets', fx_rate=fx_rate)
        book_value_ts = get_financials_ts(qfs_symbol, model=BalanceSheetAnnual, metric='total_equity', fx_rate=fx_rate)
        rnoa_ts = get_rnoa_ts(qfs_symbol)
        ato_ts = get_ato_ts(qfs_symbol)
        debt_ts = get_debt_ts(qfs_symbol, fx_rate=fx_rate)
        nr_shares_ts = get_nr_diluted_shares_ts(qfs_symbol)

        #extract revenues to give default value for valuation (bear, base, bull)
        revenues = [val for key, val in  revenue['metrics']["revenue"].items() if key != "TTM"]
        base_rev = sum(revenues)/len(revenues)
        bull_rev = max(revenues)
        bear_rev = 0.7*base_rev

        #compute op margin valuation defaults
        op_margins_vals = [val for key, val in op_margins.items() if key != "TTM"]
        base_op_margin = round(sum(op_margins_vals)/len(op_margins_vals),3)
        bull_op_margin = round(max(op_margins_vals),3)
        bear_op_margin = round(0.7*base_op_margin,3)

        #compute the NOPAT as operating income - income tax
        nopat =  {
                year: operating_income['metrics']["operating_income"][year] + income_tax['metrics']["income_tax"][year]
                for year in operating_income['metrics']["operating_income"]
                }

        #default values for cogs, sga, rnd, op asset, op liabilites, net op assets and other opex is just TTM
        cogs_val_dflt = cogs['metrics']["cogs"]["TTM"]
        sga_val_dflt = sga['metrics']["sga"]["TTM"]
        rnd_val_dflt = rnd['metrics']["rnd"]["TTM"]
        other_opex_val_dflt = other_opex['metrics']["other_opex"]["TTM"]
        op_assets_dftl = op_assets['metrics']["operating_assets"]["TTM"]
        op_liab_dftl = op_liab['metrics']["operating_liabilities"]["TTM"]
        op_net_assets_dftl = net_op_assets['metrics']["net_operating_assets"]["TTM"]
        book_value_dftl = book_value['metrics']["total_equity"]["TTM"]

        #compute gross profit defaults
        gp_dftl = [bear_rev - cogs_val_dflt, base_rev - cogs_val_dflt, bull_rev - cogs_val_dflt]
        gp_margin_dftl = [gp_dftl[0]/bear_rev if bear_rev != 0 else None, gp_dftl[1]/base_rev if base_rev != 0 else None, gp_dftl[2]/bull_rev if bull_rev != 0 else None]

        response = {'qfsSymbol' : qfs_symbol
                    ,'currency' : currency
                    ,'currencyDetected' : currency_detected
                    ,'reportingCurrency' : reporting_currency
                    ,'reportingCurrencyDetected' : reporting_currency_detected
                    ,'fxRate' : fx_rate
                    ,'nrShares' : nr_shares
                    ,'lastFetch' : last_fetch
                    ,'periods' : revenue['periods']
                    ,'metricsNopat' : {
                        'revenue' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'Revenue',
                            'topDownVisible' : True,
                            'bottomUpVisible' : True,
                            'hasTs' : True, #defines if metric has times series attached
                            'ts' : revenue_ts,
                            'values': revenue['metrics']["revenue"]
                        },
                        'cogs' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'COGS',
                            'topDownVisible' : False,
                            'bottomUpVisible' : True,
                            'hasTs' : True,
                            'ts' : cogs_ts,
                            'values': cogs['metrics']["cogs"]
                        },
                        'gross_profit' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'Gross Profit',
                            'topDownVisible' : False,
                            'bottomUpVisible' : True,
                            'fontStyle' : 'italic',
                            'hasTs' : True,
                            'ts' : cogs_ts,
                            'values': cogs['metrics']["cogs"]
                        },
                        'gp_margins' : {
                            'type' : 'perc', #percentage type will be scaled by factor 100 on frontend
                            'label' : 'Gross margin',
                            'topDownVisible' : False,
                            'bottomUpVisible' : True,
                            'fontStyle' : 'italic',
                            'hasTs' : True,
                            'ts' : gp_margin_ts,
                            'values' : gp_margins
                        },
                        'sga' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'SG&A',
                            'topDownVisible' : False,
                            'bottomUpVisible' : True,
                            'hasTs' : True,
                            'ts' : sga_ts,
                            'values': sga['metrics']["sga"]
                        },
                        'rnd' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'R&D',
                            'topDownVisible' : False,
                            'bottomUpVisible' : True,
                            'hasTs' : True,
                            'ts' : rnd_ts,
                            'values': rnd['metrics']["rnd"]
                        },
                        'other_opex' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'Other Opex',
                            'topDownVisible' : False,
                            'bottomUpVisible' : True,
                            'hasTs' : True,
                            'ts' : other_opex_ts,
                            'values': other_opex['metrics']["other_opex"]
                        },                       
                        'operating_income' : {
                            'type' : 'absolute', #has an influence if this metric is scaled or not
                            'label' : 'Op. Income',
                            'topDownVisible' : True,
                            'bottomUpVisible' : True,
                            'fontStyle' : 'italic',
                            'hasTs' : True,
                            'ts' : op_income_ts,
                            'values': operating_income['metrics']["operating_income"]
                        },
                        'op_margins' : {
                            'type' : 'perc',  #percentage type will be scaled by factor 100 on frontend
                            'label' : 'Op. Margins',
                            'topDownVisible' : True,
                            'bottomUpVisible' : True,
                            'fontStyle' : 'italic',
                            'hasTs' : True,
                            'ts' : op_margin_ts,
                            'values' : op_margins
                        },
                        'income_tax' : {
                            'type': 'absolute',
                            'label' : 'Tax',
                            'topDownVisible' : True,
                            'bottomUpVisible' : True,
                            'values' : income_tax['metrics']["income_tax"]
                        },
                        'eff_tax_rate' : {
                            'type': 'perc',
                            'label' : 'Effective Tax Rate',
                            'topDownVisible' : True,
                            'bottomUpVisible' : True,
                            'values' : effective_tr
                        },
                        'NOPAT' : {
                            'type' : 'absolute',
                            'label' : 'NOPAT',
                            'topDownVisible' : True,
                            'bottomUpVisible' : True,
                            'values' : nopat
                        }
                    },
                    'metricsNoa' : {
                        'operatingAssets' : {
                            'type' : 'absolute',
                            'label' : 'Op. Assets',
                            'hasTs' : True,
                            'ts' : op_assets_ts,
                            'values' : op_assets['metrics']["operating_assets"]
                        },
                        'operatingLiabilities' : {
                            'type' : 'absolute',
                            'label' : 'Op. Liabilities',
                            'hasTs' : True,
                            'ts' : op_liab_ts,
                            'values' : op_liab['metrics']["operating_liabilities"]
                        },
                        'netOperatingAssets' : {
                            'type' : 'absolute',
                            'label' : 'NOA',
                            'fontStyle' : 'italic',
                            'hasTs' : True,
                            'ts' : net_op_assets_ts,
                            'values' : net_op_assets['metrics']["net_operating_assets"]
                        },
                        'bookValue' : {
                            'type' : 'absolute',
                            'label' : 'Book Value',
                            'hasTs' : True,
                            'ts' : book_value_ts,
                            'values' : book_value['metrics']["total_equity"]
                        },
                       
                        'debt' : {
                            'type' : 'absolute',
                            'label' : 'Total Debt',
                            'hasTs' : True,
                            'ts' : debt_ts,
                            'values' : debt
                        },
                        'nrShares' : {
                            'type' : 'absolute',
                            'label' : 'Nr. Shares (diluted)',
                            'hasTs' : True,
                            'ts' : nr_shares_ts,
                            'values' : shares_diluted['metrics']["shares_diluted"]
                        },
                    },
                    'metricsValDrivers' : {
                        'rnoa' : {
                            'type' : 'perc',
                            'label' : 'RNOA',
                            'hasTs' : True,
                            'ts' : rnoa_ts,
                            'values' : rnoa
                        },
                        'ato' : {
                            'type' : 'absolute',
                            'label' : 'Asset Turnover',
                            'hasTs' : True,
                            'ts' : ato_ts,
                            'values' : ato
                        },
                        'op_margins' : {
                            'type' : 'perc',  #percentage type will be scaled by factor 100 on frontend
                            'label' : 'Op. Margins',
                            'hasTs' : True,
                            'ts' : op_margin_ts,
                            'values' : op_margins
                        },
                    },
                    'valuationDefaults' : {
                        'revenue' : [bear_rev, base_rev, bull_rev],
                        'cogs' : [cogs_val_dflt, cogs_val_dflt, cogs_val_dflt],
                        'gross_profit' : gp_dftl,
                        'gp_margins' : gp_margin_dftl,
                        'sga' : [sga_val_dflt, sga_val_dflt, sga_val_dflt],
                        'rnd' : [rnd_val_dflt, rnd_val_dflt, rnd_val_dflt],
                        'other_opex' : [other_opex_val_dflt, other_opex_val_dflt, other_opex_val_dflt],
                        'op_margins' : [bear_op_margin, base_op_margin, bull_op_margin],
                        'operatingAssets' : [op_assets_dftl, op_assets_dftl, op_assets_dftl],
                        'operatingLiabilities' : [op_liab_dftl, op_liab_dftl, op_liab_dftl],
                        'netOperatingAssets' : [op_net_assets_dftl, op_net_assets_dftl, op_net_assets_dftl],
                        'bookValue' : [book_value_dftl, book_value_dftl, book_value_dftl]
                    }
                    
                    }

        return Response(response)


class CorrectCurrencyAPIView(APIView):
    """
    Persists a user-confirmed correction to a company's reporting_currency and/or
    trading_currency, so future requests (and the next scheduled
    migrate_valuation_data.py / migrate_screener_data.py run) pick up the fix
    automatically instead of relying on get_fx_rate's session-only overrides every
    time. Accepts either or both fields - only the ones present get updated.

    Deliberately a separate, explicit action from those overrides - the overrides are
    also used for quick "what if" exploration and must never write to the DB on every
    keystroke; this endpoint is only called from an explicit "Save to database"
    action, since it changes what every user sees, not just the one making it.
    """
    def post(self, request):
        qfs_symbol = request.data.get("qfsSymbol")
        reporting_currency = request.data.get("reportingCurrency")
        trading_currency = request.data.get("tradingCurrency")

        if not qfs_symbol or (not reporting_currency and not trading_currency):
            return Response(
                {"detail": "qfsSymbol and at least one of reportingCurrency/tradingCurrency are required."},
                status=400,
            )

        result = {"qfsSymbol": qfs_symbol}

        with transaction.atomic():
            if reporting_currency:
                # reporting_currency lives on all six fundamentals tables (not just
                # IncomeStatementAnnual, which get_detected_currencies reads from)
                # since migrate_valuation_data.py's SQL reads it from different
                # tables depending on the function - fixing only one would leave
                # the pipeline inconsistent.
                fundamentals_models = [
                    IncomeStatementAnnual,
                    IncomeStatementQuarter,
                    BalanceSheetAnnual,
                    BalanceSheetQuarter,
                    CashFlowStatementAnnual,
                    CashFlowStatementQuarter,
                ]
                result["reportingCurrency"] = reporting_currency
                result["reportingCurrencyRowsUpdated"] = {
                    model.__name__: model.objects.filter(qfs_symbol_id=qfs_symbol).update(
                        reporting_currency=reporting_currency
                    )
                    for model in fundamentals_models
                }

            if trading_currency:
                # trading_currency lives only on TradedCompanies - it's the currency
                # last_close_price (and everything derived from it) is quoted in.
                result["tradingCurrency"] = trading_currency
                result["tradingCurrencyRowsUpdated"] = TradedCompanies.objects.filter(
                    qfs_symbol=qfs_symbol
                ).update(currency=trading_currency)

        return Response(result)


class EPVFundamentalsAPIView(APIView):
    def post(self, request):
        """
        This endpoint returns the fundamentals needed for valuing a company based on Earnings Power Value.
        The return structure will be:

        const exampleData = [
            { Revenue: [159, 237, 262] }, // bear, base, bull
            { "Operating Margin": [6.0, 9.0, 24] },
            { EBIT: [262, 16.0, 24] },
            { "D&A": [305, 3.7, 67] },
            { "Maintenance Capex": [356, 16.0, 49] },
            { "Adjusted Income": [356, 16.0, 49] },
            { "Tax Rate": [356, 16.0, 49] },
            { "Sustainable NOPAT": [356, 16.0, 49] },
            { WACC: [356, 16.0, 49] },
            { "EPV operating business": [356, 16.0, 49] },
            { Cash: [356, 16.0, 49] },
            { Debt: [356, 16.0, 49] },
            { "Nr. shares": [356, 16.0, 49] },
            { "EPV per share": [356, 16.0, 49] },
            ];

        Each value in a metric array corresponds to bear, base, bull case
        """
        #tickers is of type list
        qfs_symbols = request.data['qfs_symbols']
        today = datetime.today()

        # Format as dd-mm-yyyy
        formatted_date = today.strftime("%d-%m-%Y")

        #response list
        response = []

        for qfs_symbol in qfs_symbols:
            #check if valuation is in cache
            val_data = cache.get(f'{qfs_symbol}_EPV_{formatted_date}')

            if val_data is None:
                val_data = []
                #compute revenue: bear case = min(past 5 years), base case = avg(past 5 years), bull case = max(past 5 years)
                revenue_vals = get_revenue(qfs_symbol=qfs_symbol)
                op_margins = get_op_margin(qfs_symbol=qfs_symbol)

                #compute ebit
                ebit = [rev*op_margin if (rev is not None and op_margin is not None) else None
                         for rev, op_margin in zip(revenue_vals, op_margins)]

                #get cash (includes cash_and_equiv + st investments)
                cash = get_cash(qfs_symbol=qfs_symbol)
                cash = [cash]*3

                #get total debt
                debt = get_debt(qfs_symbol=qfs_symbol)
                debt = [debt]*3

                #get number of shares
                nr_shares = get_nr_diluted_shares(qfs_symbol=qfs_symbol)
                nr_shares = [nr_shares]*3

                #define constant values like d&a, maintenance capex, tax rate, wacc
                d_a = [0]*3
                main_capex = [0]*3
                tax_rate = [0.3]*3
                wacc = [0.11, 0.1, 0.09]

                #compute adjusted income
                adj_income = [ebit+d_a+main_capex if (ebit is not None and d_a is not None and main_capex is not None) else None
                              for ebit, d_a, main_capex in zip(ebit, d_a, main_capex)] 

                #compute sustainable nopat
                sus_nopat = [adj_inc *(1-tr) if (adj_inc is not None and tr is not None) else None
                             for adj_inc, tr in zip(adj_income, tax_rate)]

                #compute EPV operating business
                epv_op_business = [sus_nopat/wacc if (sus_nopat is not None and wacc is not None and wacc != 0) else None
                                   for sus_nopat, wacc in zip(sus_nopat, wacc)]

                #compute epv per share
                epv_per_share = [round((epv_bus + cash - debt)/nr_shares,1) if (epv_bus is not None and cash is not None and debt is not None and nr_shares is not None and nr_shares != 0) else None
                                 for epv_bus, cash, debt, nr_shares in zip(epv_op_business, cash, debt, nr_shares)]

                #get time series; time series are of the format ts = [{"year" : 2015, "value": 1000},{"year" : 2016, "value": 2000}, etc.]
                revenue_ts = get_revenue_ts(qfs_symbol=qfs_symbol)
                op_margin_ts = get_op_margin_ts(qfs_symbol=qfs_symbol)
                cash_ts = get_cash_ts(qfs_symbol=qfs_symbol)
                debt_ts = get_debt_ts(qfs_symbol=qfs_symbol)
                nr_shares_ts = get_nr_diluted_shares_ts(qfs_symbol=qfs_symbol)
                print('this is revenue_ts: ', revenue_ts)

                #create valuation dictionary; isDerived determines if the quantity is computed or not based on other companies. hasData determines if a graph is displayed for this measure on the frontend; property ts stands for time series
                val_data.append({'Revenue' : revenue_vals, 'isDerived': False, 'hasData' : True, 'ts' : revenue_ts})
                val_data.append({'Operating Margin' : op_margins, 'isDerived': False, 'hasData' : True, 'ts' : op_margin_ts})
                val_data.append({'EBIT' : ebit, 'isDerived': True, 'description': "EBIT is a derived quantity. EBIT = Revenue * Operating Margin"})
                val_data.append({'D&A' : d_a, 'isDerived': False })
                val_data.append({'Maintenance Capex' : main_capex, 'isDerived': False})
                val_data.append({'Adjusted Income' : adj_income, 'isDerived': True, 'description': "Adjusted Income is a derived quantity. Adjusted Income = EBIT + D&A - Maintenance Capex"})
                val_data.append({'Tax Rate' : tax_rate, 'isDerived': False})
                val_data.append({'Sustainable NOPAT' : sus_nopat, 'isDerived': True, 'description': "Sustainable NOPAT is a derived quantity. NOPAT = Adjusted Income*(1 - Tax Rate)"})
                val_data.append({'WACC' : wacc, 'isDerived': False})
                val_data.append({'EPV operating business' : epv_op_business, 'isDerived': True, 'description': "EPV operating business is a derived quantity. EPV operating business = Adjusted Income/Wacc"})
                val_data.append({'Cash' : cash, 'isDerived': False, 'hasData' : True, 'ts' : cash_ts})
                val_data.append({'Debt' : debt, 'isDerived': False, 'hasData' : True, 'ts' : debt_ts})
                val_data.append({'Nr. Shares' : nr_shares, 'isDerived': False, 'hasData' : True, 'ts' : nr_shares_ts})
                val_data.append({'EPV per share': epv_per_share, 'isDerived': True, 'description': "EPV per share is a derived quantity. EPV per share = (EPV operating business + Cash - Debt)/Nr. Shares"})

                # valuation = {'Revenue' : revenue_vals
                #             ,'Operating Margin' : op_margins 
                #             ,'EBIT' : ebit 
                #             ,'D&A' : d_a 
                #             ,'Maintenance Capex' : main_capex
                #             ,'Adjusted Income' : adj_income
                #             ,'Tax Rate' : tax_rate 
                #             ,'Sustainable NOPAT' : sus_nopat
                #             ,'WACC' : wacc
                #             ,'EPV operating business' : epv_op_business
                #             ,'Cash' : cash
                #             ,'Debt' : debt
                #             ,'Nr. Shares' : nr_shares
                #             ,'EPV per share': epv_per_share
                #             }


                #compute epv for ticker
                #valuation = compute_epv(qfs_symbol, op_margin_nr_years=years_op_margin,  avg_revenue_nr_years = avg_revenue_nr_years)

                #store valuation in cache
                cache.set(f'{qfs_symbol}_EPV_{formatted_date}', val_data, timeout=CACHE_TTL)
            
            
            response.append({qfs_symbol: val_data})

        return Response(response)

class PenmanFundamentalsAPIView(APIView):
    def post(self, request):
        """
        This endpoint returns the fundamentals needed for valuing a company based on Penmans valuation approach.
        Value = b0 + (RNOA_1 - wacc)*NOA_0/(1+WACC) + (RNOA_2 - wacc)*NOA_1/((1+WACC)*(r-g) --> note that we will set g to zero
        
        The return structure will be:

        const exampleData = [
            { BookValue: [159, 237, 262] }, // bear, base, bull
            { RNOA1: [0.08, 0.1, 0.12] },
            { NOA0: [262, 16.0, 24] },
            { RNOA2: [0.08, 0.1, 0.12] },
            { NOA1: [356, 16.0, 49] },
            { WACC: [0.12, 0.1, 0.08] },
            ];

        Each value in a metric array corresponds to bear, base, bull case
        """

        #tickers is of type list
        qfs_symbols = request.data['qfs_symbols']
        today = datetime.today()

        # Format as dd-mm-yyyy
        formatted_date = today.strftime("%d-%m-%Y")

        #response list
        response = []

        for qfs_symbol in qfs_symbols:
            #check if valuation is in cache
            val_data = cache.get(f'{qfs_symbol}_Penman_{formatted_date}')

            if val_data is None:
                val_data = []
                #get most recent book value
                b0 = get_book_value(qfs_symbol=qfs_symbol)
                b0 = [b0]*3

                #compute revenue: bear case = min(past 5 years), base case = avg(past 5 years), bull case = max(past 5 years)
                revenue_vals = get_revenue(qfs_symbol=qfs_symbol)
                op_margins = get_op_margin(qfs_symbol=qfs_symbol)

                #compute ebit
                ebit = [rev*op_margin if (rev is not None and op_margin is not None) else None
                         for rev, op_margin in zip(revenue_vals, op_margins)]
                
                #get net operating assets
                noa = get_noa(qfs_symbol=qfs_symbol)

                #we use a tax rate of 0.3
                tax_rate = 0.3

                #compute rnoa = ebit*(1-tr)/noa
                rnoa = [ebit*(1-tax_rate)/noa if (ebit is not None and noa is not None) else None
                        for ebit, noa in zip(ebit, noa)]
                
                #define wacc and tax rate
                wacc = [0.11, 0.1, 0.09]
                tax_rate = [tax_rate]*3
                
                #get number of shares
                nr_shares = get_nr_diluted_shares(qfs_symbol=qfs_symbol)
                nr_shares = [nr_shares]*3

                #growth (default value is zero)
                g = [0*3]

                #compute equity value and equity value per share
                equity_val = [b0 + (rnoa - wacc)*noa/(1+wacc) + (rnoa - wacc)*noa/((1+wacc)*(wacc - g)) if (b0 is not None and rnoa is not None and noa is not None and wacc is not None and g is not None) else None
                              for b0, rnoa, wacc, noa, g in zip(b0, rnoa, wacc, noa, g)]
                
                equity_val_per_share = [equity_val/nr_shares if (equity_val is not None and nr_shares is not None and nr_shares != 0) else None
                                        for equity_val, nr_shares in zip(equity_val, nr_shares)]

                #time series for revenue, op margin, RNOA, NOA, book value
                revenue_ts = get_revenue_ts(qfs_symbol=qfs_symbol)
                op_margin_ts = get_op_margin_ts(qfs_symbol=qfs_symbol)
                rnoa_ts = get_rnoa_ts(qfs_symbol=qfs_symbol)
                b0_ts = get_book_value_ts(qfs_symbol=qfs_symbol)
                noa_ts = get_noa_ts(qfs_symbol=qfs_symbol)
                nr_shares_ts = get_nr_diluted_shares_ts(qfs_symbol=qfs_symbol)

                #create valuation dictionary; isDerived determines if the quantity is computed or not based on other companies. hasData determines if a graph is displayed for this measure on the frontend; property ts stands for time series
                val_data.append({'Equity_0' : b0, 'isDerived': False, 'hasData' : True, 'ts' : b0_ts})
                val_data.append({'Revenue_1' : revenue_vals, 'isDerived': False, 'hasData' : True, 'ts' : revenue_ts})
                val_data.append({'Operating Margin_1' : op_margins, 'isDerived': False, 'hasData' : True, 'ts' : op_margin_ts})
                val_data.append({'EBIT_1' : ebit, 'isDerived': True, 'description': "EBIT is a derived quantity. EBIT = Revenue * Operating Margin"})
                val_data.append({'RNOA_1' : rnoa, 'isDerived': False, 'description': "RNOA_t = EBIT_t*(1-tax rate)/NOA_t-1", 'hasData' : True, 'ts' : rnoa_ts})
                val_data.append({'NOA_0' : noa, 'isDerived': False, 'hasData' : True, 'ts' : noa_ts})
                val_data.append({'Revenue_2' : revenue_vals, 'isDerived': False, 'hasData' : True, 'ts' : revenue_ts})
                val_data.append({'Operating Margin_2' : op_margins, 'isDerived': False, 'hasData' : True, 'ts' : op_margin_ts})
                val_data.append({'EBIT_2' : ebit, 'isDerived': True, 'description': "EBIT is a derived quantity. EBIT = Revenue * Operating Margin"})
                val_data.append({'RNOA_2' : rnoa, 'isDerived': False, 'hasData' : True, 'ts' : rnoa_ts})
                val_data.append({'NOA_1' : noa, 'isDerived': False, 'hasData' : True, 'ts' : noa_ts})
                val_data.append({'Tax Rate' : tax_rate, 'isDerived': False})
                val_data.append({'WACC' : wacc, 'isDerived': False})
                val_data.append({'Nr. Shares' : nr_shares, 'isDerived': False, 'hasData' : True, 'ts' : nr_shares_ts})
                val_data.append({'Equity Value': equity_val, 'isDerived': True, 'description': "See formula"})
                val_data.append({'Equity Value per share': equity_val_per_share, 'isDerived': True, 'description': "See formula"})


                #compute rnoa1: bear case = min(past 5 years), base case = avg 5 years, bull case = max 5 years
                # rnoa = get_rnoa(qfs_symbol=qfs_symbol)
                # noa = get_noa(qfs_symbol=qfs_symbol)
                # nopat = get_nopat(qfs_symbol=qfs_symbol)

                # revenue_vals = get_revenue(qfs_symbol=qfs_symbol)
                # op_margins = get_op_margin(qfs_symbol=qfs_symbol)

                # #compute nopat based on revenue and op margins
                # nopat_deriv = [rev*op_margin*(1-tax_rate) if (rev is not None and op_margin is not None) else None
                #          for rev, op_margin in zip(revenue_vals, op_margins)]


                # #get times series
                # rnoa_ts = get_rnoa_ts(qfs_symbol=qfs_symbol)

                # #create valuation dictionary; isDerived determines if the quantity is computed or not based on other companies. hasData determines if a graph is displayed for this measure on the frontend; property ts stands for time series
                # val_data.append({'rnoa1' : rnoa, 'isDerived': True, 'hasData' : True, 'ts' : rnoa_ts})   #, 'ts' : revenue_ts})
                # val_data.append({'rnoa2' : rnoa, 'isDerived': True, 'hasData' : True, 'ts' : rnoa_ts})   #, 'ts' : revenue_ts})
                # val_data.append({'noa0' : noa, 'isDerived': True, 'hasData' : True})   #, 'ts' : revenue_ts})
                # val_data.append({'noa1' : noa, 'isDerived': True, 'hasData' : True})   #, 'ts' : revenue_ts})
                # val_data.append({'nopat' : nopat, 'isDerived': True, 'hasData' : True})   #, 'ts' : revenue_ts})
                # val_data.append({'nopat_deriv' : nopat_deriv, 'isDerived': True, 'hasData' : True})   #, 'ts' : revenue_ts})
                # val_data.append({'op_margins' : op_margins, 'isDerived': True, 'hasData' : True})   #, 'ts' : revenue_ts})
                # val_data.append({'revenue' : revenue_vals, 'isDerived': True, 'hasData' : True})   #, 'ts' : revenue_ts})

            response.append({qfs_symbol: val_data})

        return Response(response)

def get_eps_forecasts(ticker):
    """gets eps forecasts from yahoo finance (if available for given company)"""
    #yahoo finance url
    url = f"https://finance.yahoo.com/quote/{ticker}/analysis/"

    #user-agent header to avoid being blocked by web scrapers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    #get current and next year
    current_year = datetime.now().year
    next_year = current_year + 1

    # print(f'current year and next year:{current_year} {next_year}')

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the Earnings Estimate section
        earnings_section = soup.find("section", {"data-testid": "earningsEstimate"})
        
        if earnings_section:
            #find header to extract current and next year
            headers = earnings_section.find_all("tr")

            for header in headers:
                header_cells = header.find_all("th")
                # print('these are header_cells: ', header_cells)

                if header_cells:
                    current_year_re = re.search(r"\((\d{4})\)", header_cells[-2].text.strip())
                    next_year_re = re.search(r"\((\d{4})\)", header_cells[-1].text.strip())

                    if current_year_re:
                        current_year = int(current_year_re.group(1))
                    
                    if next_year_re:
                        next_year = int(next_year_re.group(1))

            #create data structure fr eps forecast
            eps_forecast = { current_year : {'low' : 0, 'avg' : 0, 'high' : 0}, next_year : {'low' : 0, 'avg' : 0, 'high' : 0} }


            # Find the table rows
            rows = earnings_section.find_all("tr")
            
            # Extract EPS forecast for Next Year
            for row in rows:
                cells = row.find_all("td")

                #search for average estimate
                if cells and "avg" in cells[0].text.strip().lower() and "esti" in cells[0].text.strip().lower():
                    next_year_eps = cells[-1].text.strip()  # Last cell is Next Year (2026)
                    
                    eps_forecast[current_year]['avg'] = float(cells[-2].text.strip())
                    eps_forecast[next_year]['avg'] = float(cells[-1].text.strip())

                    print(f"EPS forecast for Next Year (2026): {next_year_eps}")
                    #break
                elif cells and "low" in cells[0].text.strip().lower() and "esti" in cells[0].text.strip().lower():
                    eps_forecast[current_year]['low'] = float(cells[-2].text.strip())
                    eps_forecast[next_year]['low'] = float(cells[-1].text.strip())
                elif cells and "high" in cells[0].text.strip().lower() and "esti" in cells[0].text.strip().lower():
                    eps_forecast[current_year]['high'] = float(cells[-2].text.strip())
                    eps_forecast[next_year]['high'] = float(cells[-1].text.strip())
        else:
            eps_forecast = { current_year : {'low' : 0, 'avg' : 0, 'high' : 0}, next_year : {'low' : 0, 'avg' : 0, 'high' : 0} }
            print("Earnings Estimate section not found.")
    else:
        print(f"Failed to retrieve EPS page. Status code: {response.status_code}")
        eps_forecast = { current_year : {'low' : 0, 'avg' : 0, 'high' : 0}, next_year : {'low' : 0, 'avg' : 0, 'high' : 0} }

    return eps_forecast, current_year, next_year


def initial_guess_implied_growth(wacc, residual_earnings_2):
    """Function taht returns initial guess for g that is likely to converge to the correct root"""
    g_initial = 0

    #if second residual earnings terms is negative, initial guess must be greater than wacc, otherwise we do not find root of interest
    if residual_earnings_2 < 0:
        g_initial = wacc + 0.02
    else:
        g_initial = wacc - 0.02

    return g_initial

def convert_residual_earnings_growth_to_eps_growth(residual_earnings_t, eps_t, bps_t, g, year, wacc = 0.1, nr_years = 5):
    """Converts a growth rate of residual earnings (g) into a growth rate in eps"""
    #store residual earnings
    re = [residual_earnings_t]
    eps = [eps_t]
    eps_forecast = [{'x' : year, 'y' : eps_t}]
    eps_growth_rate = []
    bps = [bps_t]

    print("initial book value: ", bps_t)
    
    
    for i in range(0,5):
        re.append(re[i]*(1+g))
        eps_t_p_1 = bps[i]*wacc + re[i+1]
        eps_forecast.append({'x' : year + i +1, 'y' : eps_t_p_1})
        eps.append(eps_t_p_1)
        bps.append(bps[i] + eps_t_p_1)


    #compute eps growth rate based on eps numbers
    for j in range(0, len(eps)-1):
        eps_growth_rate.append({'x' : year + j +1, 'y' : (eps[j+1]-eps[j])/eps[j]})


    return eps_forecast, eps_growth_rate


def compute_implicit_growth_forecast(qfs_symbol, nr_years_eps = 3, wacc = 0.1):
    """
    This computes the implicit growth in the current market price (account for value chapter 3 Stephan Penman)
    
    para ticker:
        - type: string
        - descn: ticker for which the implied growth should get computed
    
    para nr_years_eps:
        - type: integer
        - descn: if no eps forecast exists on yahoo finance, we will construct a forecast based on historical average. nr_years_eps determines how many years we use to compute the average
    
    para wacc:
        - type: string
        - descn: weighted average cost of capital
    """
    traded_company = TradedCompanies.objects.get(qfs_symbol=qfs_symbol)

    #get market price and eps forecasts from yahoo finance
    market_price, _ = get_ticker_price(traded_company.ticker, qfs_symbol)
    eps_forecast, current_year, next_year = get_eps_forecasts(traded_company.ticker)

    #assign memory to variables
    eps = []
    eps_ttm = []
    eps_valuation = [] #eps forecast for the next three years
    eps_valuation_ttm = [] #eps forecast for the next three years based on eps_ttm

    #get earnings per shares
    income_statement_annual = IncomeStatementAnnual.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')   #ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01,  ...
    income_statements_q = IncomeStatementQuarter.objects.filter(qfs_symbol_id=qfs_symbol).order_by('-period_end_date')[:4]

    #get quarterly and annual balance sheets
    balance_sheets = BalanceSheetAnnual.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')[0]  #ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01,  ...
    balance_sheet_q_minus_4 = BalanceSheetQuarter.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')[3]  #ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01,  ...

    #define function that we will use to compute implicit growth (penman page 68)
    def equation(g, market_price, b0, residual_earnings_1, residual_earnings_2, wacc):
        """Function to solve for implicit market growth contained in market price"""
        return b0 + residual_earnings_1/(1+wacc) + residual_earnings_2/ ((1+wacc) * (wacc - g)) - market_price

    #collect historical eps data
    for idx, income_statement in enumerate(income_statement_annual):
        if idx < nr_years_eps:
            eps.append(income_statement.eps_diluted)

    #collect eps data of ttm
    for income_q in income_statements_q:
        eps_ttm.append(income_q.eps_diluted)


    #check if eps forecast is not available on yahoo finance
    if eps_forecast[current_year]['avg'] == 0 or eps_forecast[next_year]['avg'] == 0:
        #average eps
        avg_eps = sum(eps)/len(eps)

        #we assume constant eps
        eps_valuation.extend([avg_eps, avg_eps])
    elif eps_forecast[current_year]['avg'] != 0 and eps_forecast[next_year]['avg'] != 0:
        eps_valuation.extend([eps_forecast[current_year]['avg'], eps_forecast[next_year]['avg']])

    #for ttm valuation we assume that eps ttm stays constant
    eps_valuation_ttm.extend([sum(eps_ttm), sum(eps_ttm)])

    #get number of shares for ticker
    nr_shares = get_nr_of_outstanding_shares(traded_company.ticker, qfs_symbol)

    #store book values per share
    bps = []
    bps_ttm = []
    bps.append(balance_sheets.total_equity/nr_shares)
    bps_ttm.append(balance_sheet_q_minus_4.total_equity/nr_shares)
    residual_earnings = []
    residual_earnings_ttm = []

    for t in range(0, len(eps_valuation)):
        #compute return on equity and residual earnings
        roce_t = eps_valuation[t]/bps[t]
        roce_t_ttm = eps_valuation_ttm[t]/bps_ttm[t]
        residual_earnings.append((roce_t - wacc)*bps[t])
        residual_earnings_ttm.append((roce_t_ttm - wacc)*bps_ttm[t]) 

        #compute next book value: b_1 = b_0 + eps
        bps.append(bps[t] + eps_valuation[t])
        bps_ttm.append(bps_ttm[t] + eps_valuation_ttm[t])

   
    #if book value is bigger than current market price --> g = 0 (no growth); in that case don't have to compute it
    if market_price is not None and bps_ttm[0] is not None:
        if bps_ttm[0] < market_price:
            #good initial guess is important as we are solving the equation iteratively; depending on sign of second residual_earnings_term we need to choose initial guess; otherwise it does not converge
            g_initial_guess = initial_guess_implied_growth(wacc, residual_earnings_ttm[1])       
            g_solution_ttm = fsolve(equation, g_initial_guess, args=(market_price, bps_ttm[0], residual_earnings_ttm[0], residual_earnings_ttm[1], wacc))
        else:
            g_solution_ttm = [0]
    else:
        g_solution_ttm = [0]

    if market_price is not None and bps[0] is not None:
        if bps[0] < market_price:
            #good initial guess is important as we are solving the equation iteratively; depending on sign of second residual_earnings_term we need to choose initial guess; otherwise it does not converge
            g_initial_guess = initial_guess_implied_growth(wacc, residual_earnings[1])
            g_solution = fsolve(equation, g_initial_guess, args=(market_price, bps[0], residual_earnings[0], residual_earnings[1], wacc))
        else:
            g_solution = [0]
    else:
        g_solution = [0]

    #check if next year is a valid value; because in yahoo finance if there does not exist an eps forecast the default year is 1970
    curr_year =  datetime.now().year
    if next_year != (curr_year + 1) and next_year != curr_year:
        next_year = curr_year + 1


    #growth rate g that we compute is a growth rate in residual earnings. We can transform that into an eps growth rate which is easier to grasp
    eps_forecast_ttm, eps_forecast_growth_rate_ttm = convert_residual_earnings_growth_to_eps_growth(residual_earnings_t=residual_earnings_ttm[1], eps_t=eps_valuation_ttm[1], bps_t=bps_ttm[2], year=next_year, g=g_solution_ttm[0], wacc = wacc)
    eps_forecast, eps_forecast_growth_rate = convert_residual_earnings_growth_to_eps_growth(residual_earnings_t=residual_earnings[1], eps_t=eps_valuation[1], bps_t=bps[2], year=next_year, g=g_solution[0], wacc = wacc)

    return {'implied_residual_earnings_growth_ttm' : g_solution_ttm[0], 'bps_q_minus_4' : bps_ttm[0], 'implied_residual_earnings_growth' : g_solution[0], 'bps_0' : bps[0], 'implied_eps_forecast': eps_forecast, 'implied_eps_growth_rate': eps_forecast_growth_rate, 'implied_eps_forecast_ttm': eps_forecast_ttm, 'implied_eps_growth_rate_ttm': eps_forecast_growth_rate_ttm}

def equity_value_residual_earnings(qfs_symbol, nr_years_eps = 3, wacc = 0.1, trends_years=5):
    """
    
    para trends_years:
        - type: integer
        - descn: number of years that are taken to display trend graphs for eps, book_value

    para nr_years_eps:
        - type: integer
        - descn: determines the number of year of historical eps numbers is used to compute an average eps. in case nore eps forecast exists for a company on yahoo finance, an averagee eps of the past nr_years_eps is computed

    para wacc:
        - type: float (smaller than 1)
        - descn: weighted average cost of capital
    
    para trends_years:
        - type: integer
        - for variables like eps and book value a time series of values is returned. the trends_years variable determines how far into the past we go
    
    """
    #get traded company object
    traded_company = TradedCompanies.objects.get(qfs_symbol=qfs_symbol)
    company_name = traded_company.name
    currency = traded_company.currency
    
    #get eps forecast from yahoo finance (if available)
    eps_forecast, current_year, next_year = get_eps_forecasts(traded_company.ticker)

    #allocate memory to values
    eps = []
    eps_trend = []
    eps_ttm = []
    eps_valuation = [] #eps forecast for the next three years
    eps_valuation_ttm = [] #eps forecast for the next three years based on eps_ttm
    book_value = [] #book value is shareholder equity
    book_value_trend = []
    roce_trend = []
    net_income = []
    net_income_ttm = []

    #with the eps forecast you can compute ROCE_t = EPS_t/BookValue_t-1
    #given ROCE_t, r, and BookValue_t-1 you can compute the first tem
    #get book value
    balance_sheets = BalanceSheetAnnual.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')  #ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01,  ...
    balance_sheet_q = BalanceSheetQuarter.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')[:4]  #ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01,  ...

    #book value most recent
    book_value_ttm = balance_sheet_q[0].total_equity
    book_value_q_minus_4 = balance_sheet_q[3].total_equity

    #get earnings per shares
    income_statement_annual = IncomeStatementAnnual.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')   #ordering is descending, so for example: 2022.12.01, 2021.12.01, 2020.12.01,  ...
    income_statements_q = IncomeStatementQuarter.objects.filter(qfs_symbol_id=qfs_symbol).order_by('-period_end_date')[:4]

    for idx, income_statement in enumerate(income_statement_annual):
        if idx < trends_years:
            eps_trend.append({'x' : income_statement.period_end_date, 'y' : income_statement.eps_diluted })
            net_income.append({'x' : income_statement.period_end_date, 'y' : income_statement.net_income })

        if idx < nr_years_eps:
            eps.append(income_statement.eps_diluted)

    for income_q in income_statements_q:
        eps_ttm.append(income_q.eps_diluted)
        net_income_ttm.append(income_q.net_income)

    #insert eps_ttm in eps_trend
    eps_trend.insert(0, {'x' : 'TTM', 'y' : sum(eps_ttm) })


    #extract book values
    for idx, balance_sheet in enumerate(balance_sheets):
        if idx < trends_years:
            book_value.append(balance_sheet.total_equity)
            book_value_trend.append({'x' : balance_sheet.period_end_date, 'y' : balance_sheet.total_equity })


    #insert most up to date book value
    book_value_trend.insert(0, {'x' :  balance_sheet_q[0].period_end_date, 'y' : book_value_ttm})


    #compute roce trend; roce is defined as: ROCE_t = EPS_t/BookValue_t-1; note that net_income and book_value are ordered in descing order, so 01.12.2024, 01.12.2023, 01.12.2022, ...
    for idx in range(0, len(book_value_trend)-1):
        try:
            roce_trend.append({ 'x' :  net_income[idx]['x'], 'y' : net_income[idx]['y']/book_value_trend[idx+1]['y']})
        except ZeroDivisionError:
            roce_trend.append({ 'x' :  net_income[idx]['x'], 'y' : 0})

    #insert the most recent roce number
    try:
        roce_trend.insert(0,{'x' : 'TTM' , 'y' : sum(net_income_ttm)/book_value_ttm})
    except ZeroDivisionError:
        roce_trend.insert(0,{'x' : 'TTM' , 'y' : 0})
      

    #check if eps forecast is not available on yahoo finance; if not we will compute average eps of past year and use it as a forecast
    if eps_forecast[current_year]['avg'] == 0 or eps_forecast[next_year]['avg'] == 0:
        #average eps
        avg_eps = sum(eps)/len(eps)

        #we assume constant eps
        eps_valuation.extend([avg_eps, avg_eps])
    elif eps_forecast[current_year]['avg'] != 0 and eps_forecast[next_year]['avg'] != 0:
        eps_valuation.extend([eps_forecast[current_year]['avg'], eps_forecast[next_year]['avg']])

    #for ttm valuation we assume that eps ttm stays constant
    eps_valuation_ttm.extend([sum(eps_ttm), sum(eps_ttm)])

    #get number of shares
    income_statement_q = IncomeStatementQuarter.objects.filter(qfs_symbol_id = qfs_symbol).order_by('-period_end_date')[0]
    nr_shares = income_statement_q.shares_diluted

    #prepare data for valuation
    bps = []
    bps_ttm = []
    bps.append(book_value[0]/nr_shares)
    bps_ttm.append(book_value_q_minus_4/nr_shares)

    #tracks terms for equity valuation; initial term is book value
    equity_value = [bps[0]]
    equity_value_ttm = [bps_ttm[0]]

    for t in range(0, len(eps_valuation)):
        #get book value
        b_0 = bps[t]

        #compute return on equity and residual earnings
        roce_t = eps_valuation[t]/bps[t]
        roce_t_ttm = eps_valuation_ttm[t]/bps_ttm[t]
        residual_earnings = (roce_t - wacc)*bps[t]
        residual_earnings_ttm = (roce_t_ttm - wacc)*bps_ttm[t]

        #check if terminal value must be computed
        if t == (len(eps_valuation)-1):
            term = residual_earnings/((1+wacc)**(t)*wacc) 
            term_ttm = residual_earnings_ttm/((1+wacc)**(t)*wacc) 
        else:
            #compute valuation term
            term = residual_earnings/(1+wacc)**(t+1)
            term_ttm = residual_earnings_ttm/(1+wacc)**(t+1)

        #compute part of equity value
        equity_value.append(term)
        equity_value_ttm.append(term_ttm)
        #compute next book value: b_1 = b_0 + eps
        bps.append(bps[t] + eps_valuation[t])
        bps_ttm.append(bps_ttm[t] + eps_valuation_ttm[t])

    #extract current share price for ticker symbol
    current_price, price_currency = get_ticker_price(traded_company.ticker, qfs_symbol)

    #sum all equity values
    return {'qfs_symbol' : qfs_symbol, 'name' : company_name, 'currency' : currency, 'equity_value_per_share' : sum(equity_value), 'equity_value_series' : equity_value, 'equity_value_per_share_ttm' : sum(equity_value_ttm), 'equity_value_series_ttm' : equity_value_ttm, 'current_price' : current_price, 'roce' : list(reversed(roce_trend)), 'eps_forecast' : eps_valuation, 'eps_forecast_ttm' : eps_valuation_ttm,   'eps' : list(reversed(eps_trend)), 'book_value' : list(reversed(book_value_trend)) ,  'price_currency' : price_currency }

class ComputeEquityValuePenmanAPIView(APIView):
    def post(self, request):

        #tickers is of type list
        qfs_symbols = request.data['qfs_symbols']
        years_eps = request.data.get('years_eps', 3) #define number of years that are used to compute average EPS
        response = []


        for qfs_symbol in qfs_symbols:
            #check if valuation is in cache
            valuation = cache.get(f'{qfs_symbol}_EquityValPenman_{years_eps}')
            growth = cache.get(f'{qfs_symbol}_GrowthPenman_{years_eps}')

            # valuation = None

            #if values not in cache we need to compute it and store in cache
            if valuation is None or growth is None:
                #values company based on stephan penman's equity valuation method; zero growth (g=0) is assumed
                valuation = equity_value_residual_earnings(qfs_symbol, nr_years_eps=years_eps)

                #computes the growth that is implied in the current market price.
                growth = compute_implicit_growth_forecast(qfs_symbol)

                #store valuation and growth in cache
                cache.set(f'{qfs_symbol}_EquityValPenman_{years_eps}', valuation, timeout=CACHE_TTL)
                cache.set(f'{qfs_symbol}_GrowthPenman_{years_eps}', growth, timeout=CACHE_TTL)

            #merge the two dictionaries
            merged_dicts = valuation | growth

            #append merged dicts to response
            response.append(merged_dicts)

        return Response(response)


def get_model_fields(model, filter_value, fields_to_exclude=[], is_custom_metric=False):
    """
    Function that returns fields of a model as a list of strings. Filter defines which model fields we want. Possible values are:
    - Key Ratios (Q)
    - Key Ratios (Y)
    - Cashflow Statement (Y)
    - Balance Sheet (Y)
    - Balance Sheet (Q)
    - Income Statement (Y)
    - valuation
    """
    return [{'techName' : field.name, 'readableName' : field.verbose_name if field.verbose_name != field.name else "", "fieldType": field.get_internal_type(), 'isCustomMetric' : is_custom_metric, 'table' : model.column_metadata[field.name] if field.name in model.column_metadata else ""} for field in model._meta.get_fields() if field.name not in fields_to_exclude and field.is_relation is False and model.column_metadata[field.name] == filter_value]

def get_custom_metrics(model):
     # Query all CustomMetrics objects
    metrics = model.objects.all()
    
    # Create a list of dictionaries using list comprehension
    return [
        {
            'techName': metric.tech_name,
            'readableName': metric.readable_name,
            # 'table': metric.table if len(metric.table.split(',')) <=1 else metric.table.split(','),
            'isCustomMetric' : True
        }
        for metric in metrics
    ]

class StockFilterAvailableQuantitiesAPIView(APIView):
    def get(self, request):
        """
        endpoint that returns all available fields that can be used as a filter for the stock screener
        {incomeStatement: ["field1", "field2", "field3", "field4", "field5", etc.], balanceSheet: ["fieldb1", "fieldb2", etc.], ...}
        """
        FIELDS_TO_EXCLUDE = ["id", "ticker", "period_end_date"]

        valuation_fields = get_model_fields(ScreenerData, filter_value="valuation", fields_to_exclude=FIELDS_TO_EXCLUDE)
        company_fields = get_model_fields(ScreenerData, filter_value="Company Info", fields_to_exclude=FIELDS_TO_EXCLUDE)
        income_y_fields = get_model_fields(ScreenerData, filter_value="Income Statement (Y)", fields_to_exclude=FIELDS_TO_EXCLUDE)
        balance_y_fields = get_model_fields(ScreenerData, filter_value="Balance Sheet (Y)", fields_to_exclude=FIELDS_TO_EXCLUDE)
        balance_q_fields = get_model_fields(ScreenerData, filter_value="Balance Sheet (Q)", fields_to_exclude=FIELDS_TO_EXCLUDE)
        cf_y_fields = get_model_fields(ScreenerData, filter_value="Cashflow Statement (Y)", fields_to_exclude=FIELDS_TO_EXCLUDE)
        kr_y_fields = get_model_fields(ScreenerData, filter_value="Key Ratios (Y)", fields_to_exclude=FIELDS_TO_EXCLUDE)
        kr_q_fields = get_model_fields(ScreenerData, filter_value="Key Ratios (Q)", fields_to_exclude=FIELDS_TO_EXCLUDE)
        customFields = get_custom_metrics(CustomMetrics)
        
        
        responseList = []

        responseBalanceSheet = {"tableName" : "Balance Sheet (Y)", "tableColumns" : balance_y_fields}
        responseCompanyFields = {"tableName" : "Company Info", "tableColumns" : company_fields}
        responseBalanceSheetQ = {"tableName" : "Balance Sheet (Q)", "tableColumns" : balance_q_fields}
        responseIncomeY = {"tableName" : "Income Statement (Y)", "tableColumns" : income_y_fields}
        responseCfY = {"tableName" : "Cashflow Statement (Y)", "tableColumns" : cf_y_fields}
        responseKrY = {"tableName" : "Key Ratios (Y)", "tableColumns" : kr_y_fields}
        responseKrQ = {"tableName" : "Key Ratios (Q)", "tableColumns" : kr_q_fields}
        responseValuation = {"tableName" : "Valuation", "tableColumns" : valuation_fields}
        responseCustomMetrics = {"tableName": "CustomMetrics", "tableColumns" : customFields}
        
        responseList.extend([responseIncomeY, responseCompanyFields, responseBalanceSheet, responseBalanceSheetQ, responseValuation, responseKrY, responseKrQ,responseCfY,responseCustomMetrics])

        responseSerialized = StockScreenerFiltersSerializer(responseList, many=True).data

        return Response(responseSerialized)


def computeAssetVal(qfs_symbol, reporting_currency_override=None, trading_currency_override=None):
        """
        returns the most recent quarterly balance sheet. Null or zero values are not returned
        """
        try:
            record = BalanceSheetQuarter.objects.filter(
                qfs_symbol_id=qfs_symbol
            ).order_by("-period_end_date").first()
        except BalanceSheetQuarter.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        # every field in BALANCE_SHEET_GROUPS is a monetary balance-sheet line item
        # (reporting currency) - convert to trading currency (see get_fx_rate) so
        # Net Liq. Value is comparable to last_close_price on the frontend. detected_*
        # stays the raw DB value regardless of overrides, for "detected -> overridden"
        # display and reverting back to it.
        reporting_currency_detected, currency_detected = get_detected_currencies(qfs_symbol)
        reporting_currency = reporting_currency_override or reporting_currency_detected
        trading_currency = trading_currency_override or currency_detected
        fx_rate = get_fx_rate(reporting_currency, trading_currency)

        data = {}
        for group_name, fields in BALANCE_SHEET_GROUPS.items():
            group_metrics = []
            for field in fields:
                value = getattr(record, field["metric"])
                if value not in (None, 0, 0.0):
                    group_metrics.append({
                        "metric": field["metric"],
                        "label": field["label"],
                        "value": value * fx_rate,
                        "multiplier" : 1
                    })
            if group_metrics:
                data[group_name] = group_metrics
            # handle case where for example no nonCurrentLiabilities are present. We return empty list
            else:
                data[group_name] = []

        #get number of shares
        nr_shares = get_nr_diluted_shares(qfs_symbol=qfs_symbol)

        return {
            "qfsSymbol": qfs_symbol,
            "periodEndDate": record.period_end_date,
            "nrShares" : nr_shares,
            "currency" : trading_currency,
            "currencyDetected" : currency_detected,
            "reportingCurrency" : reporting_currency,
            "reportingCurrencyDetected" : reporting_currency_detected,
            "fxRate" : fx_rate,
            "data": data,
             }

class AssetValFundamentalsAPIView(APIView):
    def post(self, request):
        qfs_symbols = request.data['qfs_symbols']
        # optional: override auto-detected currencies for this request only (see
        # get_fx_rate) - applies to every symbol in the batch, which in practice
        # is just the single ticker the Analysis page is currently showing.
        reporting_currency_override = request.data.get('reportingCurrency')
        trading_currency_override = request.data.get('tradingCurrency')
        has_override = bool(reporting_currency_override or trading_currency_override)
        today = datetime.today()

        # Format as dd-mm-yyyy
        formatted_date = today.strftime("%d-%m-%Y")

        #response list
        response = []

        for qfs_symbol in qfs_symbols:
            #check if value in cache
            asset_val = cache.get(f'{qfs_symbol}_AssetVal_{formatted_date}')
            asset_val = None

            if asset_val is None:
                #compute asset value
                asset_val = computeAssetVal(
                    qfs_symbol=qfs_symbol,
                    reporting_currency_override=reporting_currency_override,
                    trading_currency_override=trading_currency_override,
                )

                # don't cache an override result under the shared (non-override) cache
                # key - it would then get served to future non-override requests too
                if not has_override:
                    cache.set(f'{qfs_symbol}_AssetVal_{formatted_date}', asset_val, timeout=CACHE_TTL)


            #add asset val to response
            response.append(asset_val)

        return Response(response)

    def get(self, request, qfs_symbol):
        """
        returns the most recent quarterly balance sheet. Null or zero values are not returned
        """
        reporting_currency_override = request.query_params.get("reportingCurrency")
        trading_currency_override = request.query_params.get("tradingCurrency")
        has_override = bool(reporting_currency_override or trading_currency_override)
        today = datetime.today()

        # Format as dd-mm-yyyy
        formatted_date = today.strftime("%d-%m-%Y")

        # skip the cache entirely when overriding - a cached value could be from a
        # different (or no) override and would silently ignore this request's choice
        asset_val = None if has_override else cache.get(f'{qfs_symbol}_AssetVal_{formatted_date}')

        if asset_val is None:
            #compute asset value
            asset_val = computeAssetVal(
                qfs_symbol=qfs_symbol,
                reporting_currency_override=reporting_currency_override,
                trading_currency_override=trading_currency_override,
            )

            # don't cache an override result under the shared (non-override) cache key -
            # it would then get served to future non-override requests too
            if not has_override:
                cache.set(f'{qfs_symbol}_AssetVal_{formatted_date}', asset_val, timeout=CACHE_TTL)

        return Response(asset_val)

        # try:
        #     record = BalanceSheetQuarter.objects.filter(
        #         qfs_symbol_id=qfs_symbol
        #     ).order_by("-period_end_date").first()
        # except BalanceSheetQuarter.DoesNotExist:
        #     return Response({"detail": "Not found."}, status=404)

        # data = {}
        # for group_name, fields in BALANCE_SHEET_GROUPS.items():
        #     group_metrics = []
        #     for field in fields:
        #         value = getattr(record, field["metric"])
        #         if value not in (None, 0, 0.0):
        #             group_metrics.append({
        #                 "metric": field["metric"],
        #                 "label": field["label"],
        #                 "value": value,
        #             })
        #     if group_metrics:
        #         data[group_name] = group_metrics

        # return Response({
        #     "symbol": qfs_symbol,
        #     "period_end_date": record.period_end_date,
        #     "data": data,
        # })



class LastClosePriceAPIView(APIView):
    def get(self, request, qfs_symbol):
        """
        endpoint that returns all available fields that can be used as a filter for the stock screener
        {incomeStatement: ["field1", "field2", "field3", "field4", "field5", etc.], balanceSheet: ["fieldb1", "fieldb2", etc.], ...}
        """
        result = (
            TradedCompanies.objects
            .filter(qfs_symbol=qfs_symbol)
            .values('name', 'last_close_price', 'currency').first()
        )

        # name, last_close_price = result

        return Response({'qfsSymbol': qfs_symbol, 'lastClosePrice': result['last_close_price'], 'name' : result['name'], 'currency' : result['currency']})



class CustomMetricsAPIView(APIView):
    def get(self, request):
        """
        endpoint that returns all available fields that can be used as a filter for the stock screener
        {incomeStatement: ["field1", "field2", "field3", "field4", "field5", etc.], balanceSheet: ["fieldb1", "fieldb2", etc.], ...}
        """
        metrics = CustomMetrics.objects.filter(user=request.user)
        serializer = CustomMetricsSerializer(metrics, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CustomMetricsSerializer(data=request.data)

        #check if object is valid
        serializer.is_valid(raise_exception=True)

        #save the changes to the database
        serializer.save(user_id=request.user.id)

        #send the newly created db entry as a response along with the message
        return Response(serializer.data)

    def delete(self, request):
        """
        Deletes a saved view filter
        """
        try:
            # Step 1: Get the object by its primary key
            obj = CustomMetrics.objects.get(pk=request.data.get("id"))
            
            # Step 2: Delete the object
            obj.delete()

            #get all remaining objects and return
            custom_metrics = CustomMetrics.objects.filter(user=request.user)
            # Serialize the queryset
            serializer = CustomMetricsSerializer(custom_metrics, many=True)
            # Return the serialized data
            return Response(serializer.data)
        except Exception as e:
            print(f"An error occurred: {e}")
    
    def put(self, request):
        (employeeProfile, created) = CustomMetrics.objects.get_or_create(user_id = request.user.id)


class ValuationModelsAPIView(APIView):
    def get(self, request):
        #get qfsSymbol from queryParameters
        qfs_symbol = request.GET.get('qfsSymbol')

        #filter the ValuationModels based on qfs symbol and user
        val_models = ValuationModel.objects.filter(qfs_symbol_id = qfs_symbol, user_id = request.user.id)

        serializer = ValuationModelSerizalizer(val_models, many=True)

        return Response(serializer.data)


    def put(self, request):
        #try to extract model id from request; if it does not exist, new entry will be created
        data = request.data
        model_id = data.get("id", None)

        if model_id:
            try:
                #get existing entry
                valuation_model = ValuationModel.objects.get(id=request.data.get("id"), user_id=request.user.id)
            
                #serialize existing entry with new data
                serializer = ValuationModelSerizalizer(valuation_model, data=data, partial=True)
            except ValuationModel.DoesNotExist:
                return Response({"detail": "Model not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            #create a new entry
            serializer = ValuationModelSerizalizer(data=data)

        #check if data is valid
        if serializer.is_valid():
            serializer.save(user_id = request.user.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """
        Delete valuation model
        """
        try:
            # Step 1: Get the object by its primary key
            val_model = ValuationModel.objects.get(pk=request.data.get("id"))
            
            # Step 2: Delete the object
            val_model.delete()  

            #get all remaining objects and return
            val_models = ValuationModel.objects.filter(user_id=request.user.id, qfs_symbol_id = request.data.get('qfsSymbol'))
            # Serialize the queryset
            serializer = ValuationModelSerizalizer(val_models, many=True)
            # Return the serialized data
            return Response(serializer.data)

        except Exception as e:
            print(f"An error occurred: {e}")

class FilterViewsAPIView(APIView): 
    def get(self, request):
        user_filter_views = FilterViews.objects.filter(user=request.user)
        # Serialize the queryset
        serializer = FilterViewsSerializer(user_filter_views, many=True)
        # Return the serialized data
        return Response(serializer.data)


    # def post(self, request):
    def put(self, request):
        #extract id from request; if id is present it means that FilterView already exists, if not new object will be created
        if 'id' in request.data:
            print('id present in request data: ', request.data.get('id'))

            try:
                filter_view = FilterViews.objects.get(id=request.data.get("id"), user_id=request.user.id)
                # Update the existing object with the request data
                serializer = FilterViewsSerializer(filter_view, data=request.data, partial=True)
                
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)
            except FilterViews.DoesNotExist:
                # If the object does not exist, return a 404 error
                return Response({"detail": "Not found."})
        
        else:
            serializer = FilterViewsSerializer(data=request.data)

            #check if object is valid
            serializer.is_valid(raise_exception=True)

            #save the changes to the database
            serializer.save(user_id=request.user.id)

            #send the newly created db entry as a response along with the message
            return Response(serializer.data)
    

    def delete(self, request):
        """
        Deletes a saved view filter
        """
        try:
            # Step 1: Get the object by its primary key
            obj = FilterViews.objects.get(pk=request.data.get("id"))
            
            # Step 2: Delete the object
            obj.delete()

            #get all remaining objects and return
            user_filter_views = FilterViews.objects.filter(user=request.user)
            # Serialize the queryset
            serializer = FilterViewsSerializer(user_filter_views, many=True)
            # Return the serialized data
            return Response(serializer.data)

        except Exception as e:
            print(f"An error occurred: {e}")
   

def get_char_fields(model, fields_to_exclude=[]):
    charFields =  [field.name  for field in model._meta.get_fields() if field.is_relation is False and field.get_internal_type() in ("CharField") and field.name not in fields_to_exclude]
    return {'model' : model, 'fields' : charFields}

class CharFieldFilterOptionsAPIView(APIView): 
    def get(self, request):
        #extract all char fields and their corresponding table
        charFieldsAllTables = []
        data = {}
        charFieldsAllTables.append(get_char_fields(TradedCompanies, fields_to_exclude=["ticker", "qfs_symbol", "company_type", "name"]))
        # charFields.append(get_char_fields(TradedCompanies, fields_to_exclude=["ticker", "qfs_symbol", "company_type"]))

        for charFields in charFieldsAllTables:
            model = charFields['model']
            for field in charFields['fields']:
                distinct_values = TradedCompanies.objects.exclude(**{field: None}).values_list(field, flat=True).distinct()

                data[field] = distinct_values


        serializable_data = {'field_options': data}

        # Serialize the data
        serializer = CharFieldFilterOptions(serializable_data)
        return Response(serializer.data)





class AddColumn(APIView): 
    def post(self, request):
        # Extract data from the request
        qfs_symbols = request.data.get('qfs_symbols', [])
        field = request.data.get('field')
        #table = request.data.get('table')

        #model = get_django_model(table)
        model = ScreenerData

        # Query the database for the specified ids and field
        queryset = model.objects.filter(qfs_symbol__in=qfs_symbols)

        data = list(queryset.values('qfs_symbol', field))

        return Response(data)


class TickerSymbols(APIView): 
    def get(self, request):
        traded_companies = TradedCompanies.objects.values('id', 'qfs_symbol', 'name')
        # return Response({list(traded_companies)})
        return Response({'data' : list(traded_companies)})
    

class MicroCapClubProfiles(APIView): 
    def get(self, request):
        url = os.environ["MCC_GSHEET_URL"]
        print('this is url: ' , url)

        #define fields that will be added to response
        # Define the valuation fields and default values
        valuation_fields = [
            {'epv_per_share' : 'EPV'},
            {'epv_per_share_ttm' : 'EPV (TTM)'},
            {'penman_per_share' : 'Penman'},
            {'penman_g' : 'g'},
            {'penman_per_share_ttm' : 'Penman (TTM)' },
            {'penman_g_ttm' : 'g (TTM)'}
        ]

        #if the symbol is not found in my database, zero values will be added
        default_valuation_data = {list(item.values())[0]: 0.0 for item in valuation_fields}

        #download google sheet
        response = requests.get(url)

        if response.status_code == 200:
            #transform excel to pandas data frame
            df_dict = pd.read_excel(BytesIO(response.content), sheet_name=None)  # `sheet_name=None` loads all sheets

            # extract name of sheets; currently we only are interested in third sheet (Performance, sorted by date published)
            performance_sheet = list(df_dict.keys())[2]

            #extract the performance sheet as a dataframe
            df = df_dict[performance_sheet]  # Extract the first sheet as a DataFrame

            #extract the following columns
            columns = ['Company', 'Symbol', 'Sector', 'Member', 'DWP', 'PWP', 'Price Today/ \n*Takeout Price']
            df = df[columns]

            #rename column
            df = df.rename(columns={"Price Today/ \n*Takeout Price": "Price Today"})

            #remove all rows which have a NaN value in the Symbol column
            df = df.dropna(subset=["Symbol"]) 
            df = df.dropna(subset=["DWP"]) 

            #replace inf and na values because these are not json compliant
            df = df.replace([float("inf"), float("-inf")], None)  # Replace infinities
            df = df.where(pd.notna(df), None)  # Replace NaN with None
            df = df.astype(object).where(pd.notna(df), None)
            #transform rows of df to dictionary
            response_dict = df.to_dict(orient='records')

            #add valuation columns to reponse dict
            for item in response_dict:
                #get the microcap club (mcc) symbol
                mcc_symbol = item.get('Symbol')
                matched_company = None

                if ':' in mcc_symbol:
                    exchange, ticker = mcc_symbol.split(':', 1)
                    qfs1 = f"{ticker}:{exchange}"
                    qfs2 = f"{exchange}:{ticker}"  # just in case
                else:
                    ticker = mcc_symbol
                    qfs1 = qfs2 = None

                candidates = TradedCompanies.objects.filter(
                    Q(ticker=ticker) |
                    Q(qfs_symbol=mcc_symbol) |
                    Q(qfs_symbol=qfs1) |
                    Q(qfs_symbol=qfs2)
                )

                # Prioritize exact qfs_symbol match
                if qfs1:
                    exact_match = candidates.filter(qfs_symbol=qfs1).first()
                    if exact_match:
                        matched_company = exact_match
                    else:
                        matched_company = candidates.first()  # fallback to first candidate
                else:
                    matched_company = candidates.first()

                if matched_company:
                    valuation = Valuation.objects.filter(
                        qfs_symbol=matched_company
                    ).order_by('-valuation_date').first()

                    if valuation:
                        item.update({
                            list(item.values())[0]: getattr(valuation, list(item.keys())[0]) or 0.0 for item in valuation_fields
                        })
                    else:
                        item.update(default_valuation_data)
                else:
                    item.update(default_valuation_data)

                # #check if symbol is in format EXCHANGE:TICKER or just TICKER
                # if ':' in mcc_symbol:
                #     exchange, ticker = mcc_symbol.split(':',1)
                #     qfs_candidate = f"{ticker}:{exchange}"
                #     search_filter = Q(ticker=ticker) | Q(qfs_symbol=mcc_symbol) | Q(qfs_symbol=qfs_candidate)
                # else:
                #     ticker = mcc_symbol
                #     search_filter = Q(ticker=ticker) | Q(qfs_symbol=ticker)     

                # #try to find symbol in database
                # try:
                #     print('before q , this is earch filter: ', search_filter)
                #     traded_company = TradedCompanies.objects.get(search_filter)
                #     valuation = Valuation.objects.filter(qfs_symbol=traded_company).order_by('-valuation_date').first()

                #     if valuation:
                #         item.update({
                #             field: getattr(valuation, field) or 0.0 for field in valuation_fields
                #         })
                #     else:
                #         item.update(default_valuation_data)


                # except TradedCompanies.DoesNotExist:
                #     item.update(default_valuation_data)


            return Response(response_dict)
        else:
            return Response(
                {"error": "Failed to download the file"},
                status=status.HTTP_400_BAD_REQUEST,
            )



class PyBindExample(APIView): 
    def get(self, request):
        # result = some_fn(5,7)
        # result = extract_revenue()
        # test_list = [0.5, 1.5, 2.5, 3.5]
        # result_list = process_list(test_list)
        # #tickers = ["YRD", "AMCX", "QSG", "META", "XKLJHFSJLKH", "META"]

        tickers = list(TradedCompanies.objects.values_list('ticker', flat=True)[:5000])

        #tickers = [tickers[1315]]
        print('these are tickers: ', tickers)

        #epvs = compute_epv_cpp(tickers, 4,4,0.1,0.3)

        # for key, value_list in epvs.items():
        #     for idx, value in enumerate(value_list):
        #         if value == float('-inf') or value == float('inf'):
        #             print(f"-inf found in {key} at index {idx}; ticker: {tickers[idx]}")



        # exampleData = generate_data()
        # print('example Data: ', exampleData)
        # print('python type: ', type(exampleData))

        # # return Response({list(traded_companies)})
        # return Response({'data' : epvs})
    