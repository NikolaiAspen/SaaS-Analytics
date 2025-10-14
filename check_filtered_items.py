"""
Check what items are being filtered out as hardware
"""

import pandas as pd

# Hardware/one-time product codes to exclude
HARDWARE_CODES = {
    'Fangstr VMS', 'Fangstr Connect', 'Vertikal/Horisontal stålfeste',
    'Frakt', 'Fraktkostnad', 'Shipping', 'Hardware', 'Installasjon',
    'Oppsett', 'Setup'
}

# Invoice CSV files
invoice_files = [
    "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (3).csv",  # Jan-Jun 2024
    "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (2).csv",  # Jul-Dec 2024
    "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice (4).csv",  # Jan-Apr 2025
    "c:/Users/nikolai/Code/Saas_analyse/excel/Invoice.csv",      # May-Oct 2025
]

# Credit Note CSV
creditnote_file = "c:/Users/nikolai/Code/Saas_analyse/excel/Credit_Note.csv"

print("="*80)
print("CHECKING FILTERED ITEMS")
print("="*80)

# Load all invoice data
all_invoices = []
for file in invoice_files:
    df = pd.read_csv(file)
    df['transaction_type'] = 'invoice'
    all_invoices.append(df)
    print(f"Loaded {file.split('/')[-1]}: {len(df)} lines")

# Load credit notes
cn_df = pd.read_csv(creditnote_file)
cn_df = cn_df.rename(columns={
    'CreditNotes ID': 'Invoice ID',
    'Credit Note Number': 'Invoice Number',
    'Credit Note Date': 'Invoice Date',
    'Credit Note Status': 'Invoice Status'
})
cn_df['transaction_type'] = 'creditnote'
cn_df['Due Date'] = cn_df['Invoice Date']
all_invoices.append(cn_df)
print(f"Loaded Credit_Note.csv: {len(cn_df)} lines")

# Combine
combined_df = pd.concat(all_invoices, ignore_index=True)
print(f"\nTotal lines: {len(combined_df)}")

# Check what gets filtered
print("\n" + "="*80)
print("ITEMS FILTERED BY ITEM NAME")
print("="*80)

filtered_by_name = combined_df[combined_df['Item Name'].isin(HARDWARE_CODES)]
print(f"Total filtered by name: {len(filtered_by_name)}")
print("\nTop item names filtered:")
print(filtered_by_name['Item Name'].value_counts().head(20))

print("\n" + "="*80)
print("ITEMS FILTERED BY MISSING DESCRIPTION")
print("="*80)

filtered_by_desc = combined_df[
    combined_df['Item Desc'].isna() &
    ~(combined_df['Item Name'].str.startswith('ERS', na=False))
]
print(f"Total filtered by missing description: {len(filtered_by_desc)}")
print("\nTop item names with missing description:")
print(filtered_by_desc['Item Name'].value_counts().head(20))

# Check if we're filtering VMS products incorrectly
print("\n" + "="*80)
print("VMS PRODUCTS - Are we filtering recurring VMS?")
print("="*80)

vms_items = combined_df[combined_df['Item Name'].str.contains('VMS|vms', na=False, case=False)]
print(f"Total VMS items: {len(vms_items)}")
print("\nVMS Item Names:")
print(vms_items['Item Name'].value_counts())

print("\n" + "="*80)
print("SHOULD WE INCLUDE 'Fangstr VMS' PRODUCTS?")
print("="*80)
print("Checking if Fangstr VMS has period dates (recurring) or not (one-time)...")

fangstr_vms = combined_df[combined_df['Item Name'] == 'Fangstr VMS']
print(f"\nTotal 'Fangstr VMS' lines: {len(fangstr_vms)}")

if len(fangstr_vms) > 0:
    print("\nSample descriptions:")
    print(fangstr_vms[['Item Name', 'Item Desc', 'Item Price', 'Quantity']].head(10))
