"""Analyze September 2025 Zoho MRR report"""
import pandas as pd

file_path = r"c:\Users\nikolai\Downloads\MRR Details (2).xlsx"

try:
    # Read Zoho report
    df = pd.read_excel(file_path, skiprows=1)

    print("=== ZOHO MRR DETAILS (September 2025) ===\n")

    # Total MRR
    df['mrr_numeric'] = pd.to_numeric(df['mrr'], errors='coerce')
    total_mrr_zoho = df['mrr_numeric'].sum()

    print(f"Total MRR from Zoho: {total_mrr_zoho:,.2f} NOK")
    print(f"Total subscriptions: {len(df)}")

    # Unique customers
    unique_customers = df['customer_id'].nunique()
    print(f"Unique customers: {unique_customers}")

    # Average MRR per subscription
    avg_mrr = total_mrr_zoho / len(df)
    print(f"Average MRR per subscription: {avg_mrr:.2f} NOK")

    # ARPU
    arpu = total_mrr_zoho / unique_customers
    print(f"ARPU: {arpu:.2f} NOK")

    # Check date range
    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
    print(f"\nDate range: {df['date_parsed'].min()} to {df['date_parsed'].max()}")

    print(f"\nColumns available: {list(df.columns)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
