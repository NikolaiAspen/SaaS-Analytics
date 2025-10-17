"""
Check Excel export for invoice 2010783
"""
import pandas as pd

excel_file = r"C:\Users\nikolai\Code\Saas_analyse\excel\faktura_mrr_2025-09_September_2025.xlsx"

print("=" * 80)
print("CHECKING EXCEL EXPORT FOR ACE SJØMAT AS")
print("=" * 80)

df = pd.read_excel(excel_file)

print(f"\nColumns in Excel file:")
print(df.columns.tolist())

# Try to find the customer column
customer_col = None
for col in df.columns:
    if 'kunde' in col.lower() or 'customer' in col.lower():
        customer_col = col
        break

if customer_col:
    print(f"\nUsing customer column: {customer_col}")

    # Filter for ACE SJØMAT AS
    ace_rows = df[df[customer_col].astype(str).str.contains('ACE', na=False)]

    print(f"\nFound {len(ace_rows)} rows for ACE SJØMAT AS")
    print("\n" + "=" * 80)

    # Show all columns for ACE rows
    for idx, row in ace_rows.iterrows():
        print(f"\nRow {idx}:")
        for col in df.columns[:15]:  # Show first 15 columns
            print(f"  {col}: {row[col]}")
else:
    print("\nCould not find customer column. Showing first 5 rows:")
    print(df.head())
