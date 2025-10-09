import pandas as pd

# Read the CSV (it's easier to work with)
file_path = r"c:\Users\nikolai\Downloads\MRR_Details.csv"
df = pd.read_csv(file_path)

print("=" * 100)
print("ZOHO MRR ANALYSIS")
print("=" * 100)

# The first row contains column headers, let's fix this
# Skip first row and use second row as headers
df = pd.read_csv(file_path, skiprows=1)

print("\nColumn names after skipping header row:")
print(df.columns.tolist())

# Show first few rows
print("\nFirst 10 rows:")
print(df.head(10))

# Check if 'mrr' column exists
if 'mrr' in df.columns:
    # Convert MRR to numeric
    df['mrr'] = pd.to_numeric(df['mrr'], errors='coerce')

    # Calculate total MRR
    total_mrr = df['mrr'].sum()
    count = df['mrr'].count()

    print("\n" + "=" * 100)
    print("MRR SUMMARY FROM ZOHO EXPORT:")
    print("=" * 100)
    print(f"Total MRR (from Zoho export): {total_mrr:,.2f} NOK")
    print(f"Number of subscriptions: {count}")
    print(f"Average MRR per subscription: {total_mrr/count:,.2f} NOK")

    # Show MRR distribution
    print("\nMRR distribution:")
    print(df['mrr'].describe())

    # Show top 10 highest MRR subscriptions
    print("\nTop 10 highest MRR subscriptions:")
    top_10 = df.nlargest(10, 'mrr')[['customer_name', 'plan_name', 'mrr']]
    print(top_10.to_string())

    # Compare with our calculation
    print("\n" + "=" * 100)
    print("COMPARISON WITH OUR CALCULATION:")
    print("=" * 100)
    our_mrr = 2_434_032.35
    print(f"Our calculated MRR:    {our_mrr:>15,.2f} NOK")
    print(f"Zoho export MRR:       {total_mrr:>15,.2f} NOK")
    print(f"Difference:            {our_mrr - total_mrr:>15,.2f} NOK")
    print(f"Difference %:          {(our_mrr - total_mrr) / total_mrr * 100:>15,.2f}%")

    # Check if subscription_number or subscription_id is unique
    if 'subscription_number' in df.columns:
        unique_subs = df['subscription_number'].nunique()
        print(f"\nUnique subscription numbers: {unique_subs}")

else:
    print("\nERROR: 'mrr' column not found!")
    print("Available columns:", df.columns.tolist())
