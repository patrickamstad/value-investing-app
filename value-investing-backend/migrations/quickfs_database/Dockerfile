FROM python:3.13.3-slim AS dev

# avoid buffering standard output (logs will be shown immediately)
ENV PYTHONUNBUFFERED=1

# copy requirements.txt and and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#copy application code
COPY . .


FROM --platform=linux/amd64 python:3.13.3-slim AS prd

# avoid buffering standard output (logs will be shown immediately)
ENV PYTHONUNBUFFERED=1

# copy requirements.txt and and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#copy application code
COPY . .

# make entrypoint file executable
#RUN chmod +x migrate_quickfs_db_prd.sh

#ENTRYPOINT ["sh", "./migrate_quickfs_db_prd.sh"]

CMD ["sh", "-c", "python download_eodhd_data.py && python main.py && python migrate_close_prices.py && python migrate_op_assets_and_liabilities.py && python migrate_fx_rates.py && python migrate_valuation_data.py && python migrate_screener_data.py"]
