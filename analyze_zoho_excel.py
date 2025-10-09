import pandas as pd

# Read the Excel file
file_path = r"c:\Users\nikolai\Downloads\MRR Details.xlsx"
df = pd.read_excel(file_path)

print("=" * 100)
print("ZOHO MRR DETAILS - COLUMN ANALYSIS")
print("=" * 100)

# Show all columns
print("\nColumns in the file:")
print(df.columns.tolist())

# Show first few rows
print("\nFirst 10 rows:")
print(df.head(10).to_string())

# Show data types
print("\nData types:")
print(df.dtypes)

# Show summary statistics for numeric columns
print("\nNumeric columns summary:")
print(df.describe())

# Check for MRR-related columns
mrr_columns = [col for col in df.columns if 'mrr' in col.lower() or 'amount' in col.lower() or 'total' in col.lower() or 'price' in col.lower()]
print(f"\nMRR/Amount related columns: {mrr_columns}")

# If there's an MRR column, calculate total
if mrr_columns:
    for col in mrr_columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            total = df[col].sum()
            print(f"Total {col}: {total:,.2f}")

# Show sample data for key columns
print("\n" + "=" * 100)
print("SAMPLE DATA FOR KEY COLUMNS:")
print("=" * 100)
if len(df) > 0:
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            print(f"\n{col}:")
            print(f"  Sample values: {df[col].head(5).tolist()}")
            print(f"  Sum: {df[col].sum():,.2f}")
            print(f"  Count: {df[col].count()}")

# Save to CSV for easier viewing
csv_path = r"c:\Users\nikolai\Downloads\MRR_Details.csv"
df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"\n\nSaved to CSV: {csv_path}")
