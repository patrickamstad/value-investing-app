import os
from dotenv import load_dotenv
from eodhd_price_fetch import update_close_prices_via_eodhd_bulk

load_dotenv()

print("#######################################")
print("Start migrating close prices")
print("#######################################\n\n\n")

update_close_prices_via_eodhd_bulk(
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    eodhd_api_token=os.environ["EODHD_API_TOKEN"],
    db_update_chunk_size=3000,
)

print("#######################################")
print("End migrating close prices")
print("#######################################\n\n\n")
