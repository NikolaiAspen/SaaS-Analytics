"""Analyze Zoho MRR Details report"""
import pandas as pd
import sys

file_path = r"c:\Users\nikolai\Downloads\MRR Details (1).xlsx"

try:
    # Read the Excel file
    df = pd.read_excel(file_path, skiprows=1)

    print("=== ZOHO MRR DETAILS REPORT ===\n")
    print(f"Total rows: {len(df)}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nFirst few rows:")
    print(df.head(10).to_string())

    # Try to find MRR column
    mrr_col = None
    for col in df.columns:
        if 'mrr' in str(col).lower():
            mrr_col = col
            break

    if mrr_col:
        df['mrr_numeric'] = pd.to_numeric(df[mrr_col], errors='coerce')
        total_mrr = df['mrr_numeric'].sum()
        print(f"\n=== SUMMARY ===")
        print(f"Total MRR: {total_mrr:,.2f} NOK")
        print(f"Number of subscriptions: {len(df)}")

        # Check if there's a date column
        date_col = None
        for col in df.columns:
            if 'date' in str(col).lower():
                date_col = col
                break

        if date_col:
            df['date_parsed'] = pd.to_datetime(df[date_col], errors='coerce')
            if df['date_parsed'].notna().any():
                first_date = df['date_parsed'].min()
                last_date = df['date_parsed'].max()
                print(f"Date range: {first_date} to {last_date}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
