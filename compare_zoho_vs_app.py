"""Compare Zoho report with our app's calculation"""
import pandas as pd

file_path = r"c:\Users\nikolai\Downloads\MRR Details (1).xlsx"

try:
    # Read Zoho report
    df = pd.read_excel(file_path, skiprows=1)

    print("=== ZOHO MRR DETAILS (October 2024) ===\n")

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

    # Look at created_at to understand subscription ages
    df['created_parsed'] = pd.to_datetime(df['created_at'], errors='coerce')

    # Count by creation date
    print(f"\n=== Subscription Age Distribution ===")
    df['year_created'] = df['created_parsed'].dt.year
    print(df['year_created'].value_counts().sort_index())

    # Top 10 MRR values
    print(f"\n=== Top 10 MRR Values ===")
    top_10 = df.nlargest(10, 'mrr_numeric')[['customer_name', 'plan_name', 'mrr']]
    print(top_10.to_string(index=False))

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
