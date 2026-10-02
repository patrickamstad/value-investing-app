#!/bin/bash
set -e

# define image name
IMAGE_NAME="migrate_quickfs_db"


# Build the migration image
docker build --target dev -t $IMAGE_NAME  .

TEMP_VOLUME="temp_data_volume"
docker volume create $TEMP_VOLUME

# Run container on the same network with .env file
docker run --rm \
  --network value-investing-app_value_investing_app_ntw \
  --env-file .env \
  -v $TEMP_VOLUME:/Data \
  --name  $IMAGE_NAME \
  $IMAGE_NAME \
  sh -c "python migrate_screener_data.py && sleep 300"


# Full chain (main.py onward) - restore this for the next from-scratch run:
#  sh -c "python main.py --type bulk && python migrate_close_prices.py && python migrate_op_assets_and_liabilities.py && python migrate_fx_rates.py && python migrate_valuation_data.py && python migrate_screener_data.py && sleep 300"

#  sh -c "python download_eodhd_data.py && python main.py --type bulk && python migrate_close_prices.py && python migrate_op_assets_and_liabilities.py && python migrate_fx_rates.py && python migrate_valuation_data.py && python migrate_screener_data.py && sleep 300"

# delete volume as it is no longer needed
 docker volume rm $TEMP_VOLUME
