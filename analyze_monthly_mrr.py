import pandas as pd

# Read the monthly MRR report
file_path = r"c:\Users\nikolai\Downloads\Monthly Recurring Revenue (MRR).xlsx"

# Try to read the file - Excel files from Zoho often have headers in first few rows
df = pd.read_excel(file_path)

print("=" * 100)
print("ZOHO MONTHLY MRR REPORT ANALYSIS")
print("=" * 100)

print("\nRaw columns:")
print(df.columns.tolist())

print("\nFirst 20 rows (raw):")
print(df.head(20))

# Try skipping header rows
for skip_rows in [0, 1, 2, 3, 4]:
    try:
        df_test = pd.read_excel(file_path, skiprows=skip_rows)
        print(f"\n\n=== WITH skiprows={skip_rows} ===")
        print("Columns:", df_test.columns.tolist())
        print("\nFirst 5 rows:")
        print(df_test.head(5))

        # Check if this looks like the right format
        if 'mrr' in str(df_test.columns).lower() or 'month' in str(df_test.columns).lower():
            print("\n*** This looks like the right format! ***")

            # Save to CSV for easier analysis
            csv_path = r"c:\Users\nikolai\Downloads\Monthly_MRR.csv"
            df_test.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"Saved to: {csv_path}")
            break
    except Exception as e:
        print(f"Skip {skip_rows} failed: {e}")
