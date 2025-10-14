import pandas as pd

# Load credit notes
cn = pd.read_excel('excel/Credit_Note.xlsx')

# Load parameters
params = pd.read_excel('c:/Users/nikolai/Downloads/parameters.xlsx')
params_allowed = params[params['Inntektsgruppe'].isin(['Fangstdagbok', 'Support', 'VMS'])]

# Get unique item names
cn_items = set(cn['Item Name'].unique())
params_items = set(params_allowed['Item name'].unique())

# Find matches
matched = cn_items.intersection(params_items)
unmatched = cn_items - params_items

print(f'Credit Note unique items: {len(cn_items)}')
print(f'Parameters (allowed groups): {len(params_items)}')
print(f'Matched items: {len(matched)}')
print(f'Match rate: {len(matched)/len(cn_items)*100:.1f}%')

print('\n\nTop 10 matched items:')
for item in list(matched)[:10]:
    print(f'  - {item}')

print('\n\nUnmatched items (first 10):')
for item in list(unmatched)[:10]:
    # Count how many times this item appears
    count = len(cn[cn['Item Name'] == item])
    print(f'  - {item} ({count} occurrences)')
