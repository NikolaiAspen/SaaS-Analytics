"""
Inspect Excel file structure to understand available data
"""
import pandas as pd
import os

def inspect_excel(file_path):
    print(f"\n{'='*80}")
    print(f"File: {os.path.basename(file_path)}")
    print('='*80)

    try:
        # Read with skiprows=1 (like in the import code)
        df = pd.read_excel(file_path, skiprows=1)

        print(f"\nTotal rows: {len(df)}")
        print(f"\nColumns ({len(df.columns)}):")
        for i, col in enumerate(df.columns):
            print(f"  {i}: {col}")

        print(f"\nFirst 3 rows:")
        print(df.head(3).to_string())

        # Look for MRR-related columns
        print(f"\nMRR-related columns:")
        for col in df.columns:
            col_lower = str(col).lower()
            if 'mrr' in col_lower or 'revenue' in col_lower or 'amount' in col_lower:
                print(f"  - {col}")
                print(f"    Sample values: {df[col].head(3).tolist()}")

    except Exception as e:
        print(f"Error: {e}")

# Check different types of files
print("Inspecting MRR Details files...")
inspect_excel("excel/MRR Details.xlsx")
inspect_excel("excel/MRR Details (1).xlsx")

print("\n\nInspecting Monthly files...")
inspect_excel("excel/Oct2024.xlsx")
inspect_excel("excel/Nov2024.xlsx")

print("\n\nInspecting Churn files...")
inspect_excel("excel/ChurnJan25.xlsx")
inspect_excel("excel/ChurnFeb25.xlsx")
