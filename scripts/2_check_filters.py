import os
import sys
import polars as pl

# ------------------------------------------------------------------------------
# 1. LOCATE PARQUET FILE
# ------------------------------------------------------------------------------
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(project_root, "data")
parquet_path = os.path.join(data_dir, "aws_ec2_pricing.parquet")

if not os.path.exists(parquet_path):
    print(f"Error: Could not find '{parquet_path}'")
    print("Please run 01_ingest_data.py first to generate the Parquet file.")
    sys.exit(1)

print(f"Reading Parquet File: {parquet_path}")
print("=" * 60)

# ------------------------------------------------------------------------------
# 2. LOAD DATASET
# ------------------------------------------------------------------------------
df = pl.read_parquet(parquet_path)


print(f"Dataset Overview")
print(f"Total Rows in Parquet: {df.height:,}")
print(f"Total Columns in Parquet: {len(df.columns)}")
print("=" * 60)

# ------------------------------------------------------------------------------
# 3. CHECK COLUMN NAMES (SNAKE_CASE VERIFICATION
# ------------------------------------------------------------------------------
print("snake_case Check")

non_snake_cols = [c for c in df.columns if not c.islower() or " " in c or "/" in c]
if not non_snake_cols:
    print("All columns match with the farmat of snake_case")
else:
    print(f"Most of the columns match with the farmat of snake_case excapt ：{non_snake_cols}")

print("\nColumn List：")
for idx, col in enumerate(df.columns, 1):
    print(f"  {idx:2d}. {col}")

print("=" * 60)
# ------------------------------------------------------------------------------
# 4. VERIFY FILTERED COLUMNS
# ------------------------------------------------------------------------------
filter_columns = ["location", "term_type", "operating_system", "tenancy", "unit", 
                  "lease_contract_length", "purchase_option", "capacity_status"]

for col in filter_columns:
    if col in df.columns:
        unique_vals = df[col].drop_nulls().unique().to_list()
        print(f"\n Distinct Values in '{col}' ({len(unique_vals)} found):")
        for val in sorted(unique_vals):
            print(f"   • {val}")
    else:
        print(f"\nColumn '{col}' not found in Parquet schema!")

# Check price_per_unit Range
if "price_per_unit" in df.columns:
    price_series = df["price_per_unit"].cast(pl.Float64, strict=False).drop_nulls()
    min_price = price_series.min()
    max_price = price_series.max()
    print(f"\n 'price_per_unit' Range:")
    print(f"   • Min Price: ${min_price}")
    print(f"   • Max Price: ${max_price}")
else:
    print("\nColumn 'price_per_unit' not found in Parquet schema!")

print("\n" + "=" * 60)
print("Verification Complete!")