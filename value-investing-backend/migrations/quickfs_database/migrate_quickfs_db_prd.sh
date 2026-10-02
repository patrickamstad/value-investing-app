#!/bin/bash
set -e

# Check file exists
#if [ ! -f .env.prd ]; then
#    echo ".env.prd file not found!"
#    exit 1
#fi

# Export all variables
#set -a
#source .env.prd
#set +a

# Run migration scripts
python download_eodhd_data.py
python main.py
python migrate_close_prices.py
python migrate_op_assets_and_liabilities.py
python migrate_fx_rates.py
python migrate_valuation_data.py
python migrate_screener_data.py

echo "Production migration completed successfully!"