"""
Check if the MRR discrepancy can be explained by VAT (MVA)

Norwegian VAT is 25%, which means:
- Amount with VAT = Amount without VAT * 1.25
- Amount without VAT = Amount with VAT / 1.25
"""

# Our calculated MRR
our_mrr = 2_434_032.35

# Zoho's reported MRR
zoho_mrr = 2_057_856.53

# Calculate the ratio
ratio = our_mrr / zoho_mrr
print(f"Our MRR: {our_mrr:,.2f} NOK")
print(f"Zoho MRR: {zoho_mrr:,.2f} NOK")
print(f"Ratio: {ratio:.4f}")
print()

# Check if it's VAT related
print("Theory 1: Our amounts INCLUDE 25% VAT, Zoho's MRR EXCLUDES VAT")
mrr_without_vat = our_mrr / 1.25
print(f"Our MRR without VAT (÷ 1.25): {mrr_without_vat:,.2f} NOK")
print(f"Difference from Zoho: {mrr_without_vat - zoho_mrr:,.2f} NOK")
print(f"Difference %: {(mrr_without_vat - zoho_mrr) / zoho_mrr * 100:.2f}%")
print()

print("Theory 2: Maybe it's a different tax rate?")
# What tax rate would explain the difference?
implied_tax_rate = (our_mrr / zoho_mrr - 1) * 100
print(f"Implied tax/markup rate: {implied_tax_rate:.2f}%")
print()

print("Theory 3: Some subscriptions might be excluded")
# If some subscriptions should be excluded
excluded_amount = our_mrr - zoho_mrr
print(f"Amount that might be excluded: {excluded_amount:,.2f} NOK")
print(f"As percentage of our MRR: {excluded_amount / our_mrr * 100:.2f}%")
print()

print("Conclusion:")
print("=" * 80)
if abs(mrr_without_vat - zoho_mrr) < 200000:  # Within 200k
    print("✓ VAT (25%) explains the discrepancy well!")
    print("  Solution: Use 'sub_total' field instead of 'amount' from Zoho API")
elif ratio < 1.2:
    print("✓ Likely a tax-related issue, but not exactly 25%")
    print("  Check if Zoho sends a tax-exclusive amount field")
else:
    print("✗ The discrepancy is NOT explained by VAT alone")
    print("  Other factors might be involved")
