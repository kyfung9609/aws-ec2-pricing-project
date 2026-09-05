import os
import sys
import polars as pl

# ------------------------------------------------------------------------------
# 1. LOCATE PARQUET FILE & DEFINE OUTPUT CSV PATH
# ------------------------------------------------------------------------------
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(project_root, "data")
parquet_path = os.path.join(data_dir, "aws_ec2_pricing.parquet")
csv_path = os.path.join(data_dir, "aws_ec2_pricing.csv")

if not os.path.exists(parquet_path):
    print(f"❌ Error: Could not find '{parquet_path}'")
    print("Please run 01_ingest_data.py first to generate the Parquet file.")
    sys.exit(1)

print(f"📂 Reading Parquet file: {parquet_path}")

# ------------------------------------------------------------------------------
# 2. READ PARQUET & WRITE TO CSV
# ------------------------------------------------------------------------------
df = pl.read_parquet(parquet_path)
print(f"📊 Total rows to export: {df.height:,}")

# Export to CSV
df.write_csv(csv_path)

print("\n" + "=" * 60)
print(f"✅ Successfully exported to CSV!")
print(f"📁 Output Location: {csv_path}")
print(f"📦 CSV Output Size: {os.path.getsize(csv_path) / (1024 * 1024):.2f} MB")
print("=" * 60)