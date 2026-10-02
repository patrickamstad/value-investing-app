"""
One-off script: populate download_progress.txt from symbols already in S3.
Run this once after introducing download_progress.txt to avoid re-fetching
symbols that were downloaded in a previous run.
"""

import os
from pathlib import Path
import boto3
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = "eodhd-fundamentals"
PROGRESS_FILE = Path(__file__).parent / "download_progress.txt"

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

symbols = []
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX + "/"):
    for obj in page.get("Contents", []):
        filename = obj["Key"].rsplit("/", 1)[-1]
        if filename.endswith(".json"):
            symbols.append(filename[:-5])  # "AAPL.US.json" → "AAPL.US"

PROGRESS_FILE.write_text("\n".join(symbols) + "\n" if symbols else "")
print(f"Written {len(symbols)} symbols to {PROGRESS_FILE}")
