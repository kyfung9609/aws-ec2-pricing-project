import csv
import os
import sys
import kagglehub
import polars as pl
import re

# ------------------------------------------------------------------------------
# 1. DOWNLOAD & LOCATE DATASET
# ------------------------------------------------------------------------------
print("🚀 [Step 1/7] Downloading dataset from Kaggle...")
dataset_path = kagglehub.dataset_download("justsahil/aws-pricing-dataset")

target_csv = None
max_size = 0

for root, _, files in os.walk(dataset_path):
    for file in files:
        if file.endswith(".csv"):
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            if file_size > max_size:
                max_size = file_size
                target_csv = file_path

if not target_csv or max_size == 0:
    print(f"❌ Error: CSV file is missing or corrupted in {dataset_path}.")
    sys.exit(1)

print(f"Target CSV: {target_csv} ({max_size / (1024 * 1024):.2f} MB)")

# ------------------------------------------------------------------------------
# 2. DYNAMIC HEADER DETECTION
# ------------------------------------------------------------------------------
print("\n[Step 2/7] Detecting true CSV header row...")

skip_count = 0
all_columns = []

with open(target_csv, "r", encoding="utf-8", errors="ignore") as f:
    lines = [f.readline() for _ in range(10)]
    max_cols = 0
    best_line_idx = 0
    
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        cols = next(csv.reader([line]))
        if len(cols) > max_cols:
            max_cols = len(cols)
            best_line_idx = idx

    skip_count = best_line_idx
    all_columns = next(csv.reader([lines[best_line_idx]]))

print(f"Header detected on Line {skip_count + 1} (Skipping {skip_count} metadata rows)")

# ------------------------------------------------------------------------------
# 3. DEFINE TARGET COLUMNS TO INGEST
# ------------------------------------------------------------------------------
preferred_columns = [
    # Identifiers & Terms / Pricing & Identifiers
    "SKU", "OfferTermCode", "RateCode", "TermType", "PriceDescription", 
    "LeaseContractLength", "PurchaseOption",
    "EffectiveDate", "PricePerUnit", "Unit", "Currency",

    # Product & Service
    "serviceCode", "Product Family",

    # Location
    "Location", "Location Type", "Region Code", 
    
    # Compute Hardware Specs
    "Instance Type", "vCPU", "Memory", "Storage", "Network Performance", 
    "Clock Speed", "Processor Architecture", "Physical Processor",
    
    # Software & Operating Environment (exact CSV camelCase names)
    "Operating System", "Tenancy", "Pre Installed S/W", "License Model",
    
    # Deployment & Operations
    "usageType", "operation", "CapacityStatus"
]

# Select only existing columns
selected_columns = [col for col in preferred_columns if col in all_columns]
print(f"Selected {len(selected_columns)} analytical columns for ingestion.")

# ------------------------------------------------------------------------------
# 4. INGEST & FILTER WITH POLARS
# ------------------------------------------------------------------------------
print("\n[Step 3/7] Processing data with Polars...")

df = pl.read_csv(
    target_csv,
    skip_rows=skip_count,
    columns=selected_columns,
    infer_schema_length=10000,
    ignore_errors=True,
    truncate_ragged_lines=True
)

print(f"Raw ingested rows: {df.height:,}")

target_locations = [
    "Canada (Central)",
    "Canada West (Calgary)",
    "US East (N. Virginia)"
]

print("\n [Step 4/7] Applying filters...")

# Cast PricePerUnit numeric type before comparison
df = df.with_columns(
    pl.col("PricePerUnit").cast(pl.Float64, strict=False).alias("PricePerUnit")
)

df_filtered = df.filter(
    (pl.col("Location").is_in(target_locations)) &
    (pl.col("Operating System").is_in (["Linux", "Windows"])) &
    (pl.col("CapacityStatus") == "Used") &
    (pl.col("Tenancy") == "Shared") &
    (pl.col("PricePerUnit") > 0) &
    # Exclude AWS Wavelength Zones (e.g. ca-central-1-wl1-yto1): these are
    # carrier-embedded edge compute, not standard regional EC2 capacity, and
    # share their parent region's "Location" label so the filter above alone
    # doesn't catch them. Wavelength region codes always contain "-wl".
    (~pl.col("Region Code").str.contains("-wl", literal=True).fill_null(False))
)

print(f"Filtered rows remaining: {df_filtered.height:,}")

# ------------------------------------------------------------------------------
# 6. MODIFY COLUMN NAMES
# ------------------------------------------------------------------------------
print("\n [Step 5/7] Modifying column names...")
def to_snake_case(name: str) -> str:
    name = re.sub(r'[\\/]', '', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    name = re.sub(r'[\s\-]+', '_', name)
    return name.lower().strip('_')

column_mapping = {col: to_snake_case(col) for col in df_filtered.columns}
df_filtered = df_filtered.rename(column_mapping)

# ------------------------------------------------------------------------------
# 7. EXTRACT FEATURES
# ------------------------------------------------------------------------------
print("\n [Step 6/7] Extracting feature...")
df_filtered = df_filtered.with_columns([
    # Extract instance_family (e.g. "c6i.xlarge" -> "c6i")
    pl.col("instance_type").str.split(".").list.get(0).alias("instance_family"),
    # Extract instance_size (e.g. "c6i.xlarge" -> "xlarge")
    pl.col("instance_type").str.split(".").list.get(1).alias("instance_size")
])

# Extract hardware_generation from instant_faily (e.g. "c6i" -> 6)
df_filtered = df_filtered.with_columns([
    pl.col("instance_family")
      .str.extract(r"(\d+)", 1)
      .cast(pl.Int32, strict=False)
      .alias("hardware_generation"),

# Classify processor_vendor (Intel / AMD / AWS Graviton)
pl.when(pl.col("instance_family").str.ends_with("g"))
      .then(pl.lit("AWS Graviton"))
      .when(pl.col("instance_family").str.ends_with("a"))
      .then(pl.lit("AMD"))
      .otherwise(pl.lit("Intel"))
      .alias("processor_vendor")
])

# ------------------------------------------------------------------------------
# 8. EXPORT CLEAN DATASET
# ------------------------------------------------------------------------------
print("\n [Step 7/7] Exporting processed dataset...")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_dir = os.path.join(project_root, "data")
os.makedirs(output_dir, exist_ok=True)

parquet_path = os.path.join(output_dir, "aws_ec2_pricing.parquet")

categorical_cols = ["location", "operating_system", "tenancy", "term_type"]
df_filtered = df_filtered.with_columns([
    pl.col(col).cast(pl.Categorical) for col in categorical_cols if col in df_filtered.columns
])


df_filtered.write_parquet(parquet_path, compression="zstd")

print(f"Ingestion complete! Clean file saved to: {parquet_path}")
print(f"Final Output Size: {os.path.getsize(parquet_path) / (1024 * 1024):.2f} MB")