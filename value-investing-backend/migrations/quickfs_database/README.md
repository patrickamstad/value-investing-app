# EODHD Fundamentals Migration

## Two data sources

### Historical (full data) — `eodhd-fundamentals/`

Built once by `download_eodhd_data.py`. Fetches each ticker individually at 1 API call per ticker. Stores **complete historical data** going back as far as EODHD has records.

```bash
python download_eodhd_data.py
python main.py                    # default, reads eodhd-fundamentals/
```

**Cost:** ~1 call per ticker which costs 10 requests. With 100K daily credits this covers ~100K tickers per day, so a full download takes several days for large exchanges.

---

### Bulk (daily refresh) — `eodhd-fundamentals-bulk/`

Built daily by `download_eodhd_bulk.py`. Uses the EODHD bulk endpoint: 100 credits per request, 500 companies returned. With 100K daily credits that covers 500K companies per day — enough to refresh every exchange in a single run.

**Limitation:** bulk data is truncated to the last 4 annual and 4 quarterly periods. The historical S3 files are never touched.

```bash
python download_eodhd_bulk.py     # writes to eodhd-fundamentals-bulk/
python main.py --type bulk        # reads eodhd-fundamentals-bulk/
```

---

## When to use which

| | Historical | Bulk |
|---|---|---|
| **Run** | Once (or to backfill) | Daily |
| **Data depth** | Full history | Last 4 years / 4 quarters |
| **API cost** | 1 call / ticker | 100 calls / 500 tickers |
| **S3 prefix** | `eodhd-fundamentals/` | `eodhd-fundamentals-bulk/` |
| **Use case** | Initial load, DCF back-testing | Keeping recent periods up to date |

The two S3 prefixes are intentionally separate — running the bulk download never overwrites historical files.

---

## Resuming interrupted runs

Both download scripts track progress in a local text file (one completed exchange per line). Delete the file to start from scratch.

| Script | Progress file |
|---|---|
| `download_eodhd_data.py` | `download_progress.txt` |
| `download_eodhd_bulk.py` | `bulk_download_progress.txt` |
