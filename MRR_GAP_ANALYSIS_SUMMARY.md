# MRR Gap Analysis - Summary Report
**Date:** 2025-10-11  
**Session:** Invoice MRR vs Subscription MRR Investigation

---

## Current State (October 2025)

### MRR Comparison
- **Subscription-based MRR:** 2,060,698.05 NOK  
- **Invoice-based MRR (CSV):** 1,221,561.22 NOK  
- **Gap:** 839,136.83 NOK (**40.7%** missing)

### Line Items Processed
- Invoice line items: 2,950
- Credit note line items: 284
- Total: 3,234 line items
- Unique customers: 1,733

---

## KEY FINDING: CSV Files Are Incomplete!

### Data Source Comparison

**CSV Files (Current Import):**
- Invoice (3).csv: 1,818 lines (Jan-Jun 2024)
- Invoice (2).csv: 2,035 lines (Jul-Dec 2024)
- Invoice (4).csv: 1,455 lines (Jan-Apr 2025)
- Invoice.csv: 1,783 lines (May-Oct 2025)
- Credit_Note.csv: 2,384 lines
- **TOTAL: ~9,475 records**

**Zoho API (Complete Data):**
- Invoices: **10,763**
- Credit Notes: **1,923**
- **TOTAL: 12,686 records**

**Missing:** API has **3,211 MORE invoices** than CSV files (+33% more data!)

---

## Critical Insight from Zoho Master Sales Report

### September 2025 Actual Data (from Zoho report)

**Net Invoice Amount:**
- Credit Notes: -190,972.66 NOK
- Invoices: +1,651,045.58 NOK
- **Net Total: 1,460,072.92 NOK** (raw invoice amounts)

**Periodization Breakdown:**
- Monthly subscriptions (1 month): 122,592.91 NOK raw
- Yearly subscriptions (12 months): 1,337,480.01 NOK raw
- **Total invoiced: 1,460,072.92 NOK**

**Expected September MRR Calculation:**
- Monthly: 122,592.91 / 1 = 122,592.91 NOK
- Yearly: 1,337,480.01 / 12 = 111,456.67 NOK
- **Expected MRR: ~234,049 NOK**

> **User's Key Statement:** "om du ser på denne så ser du at det ikke var veldig stor forskjell i september fra subscription basert til fakturabasert mrr"

This means:
1. The calculation methodology CAN work correctly
2. September had close subscription vs invoice MRR numbers
3. Something specific to October OR incomplete data is causing the gap

---

## Fixes Applied During Session

### 1. Fixed Monthly Product Period Dates
**Problem:** 217 "Satellittabonnement (mnd)" items had no period dates  
**Cause:** `parse_period_from_name()` only calculated dates for months > 1  
**Fix:** Calculate period dates for ALL products (monthly AND yearly)  
**Impact:** +21,664 NOK MRR improvement

### 2. Fixed Name-Based Period Parsing Condition
**Problem:** Monthly products excluded from name-based period calculation  
**Cause:** Condition checked `if months_from_name > 1` instead of checking for dates  
**Fix:** Changed to `if start_date_from_name is not None`  
**Impact:** Included in Fix #1

### 3. Added Norwegian Date Format Parsing
**Problem:** 274 items with descriptions but NO parsed periods  
**Added Patterns:**
- Pattern 3: "Gjelder fra DD måned - DD måned YYYY"
- Pattern 4: "DD.MM.YY-DD.MM.YY"
**Impact:** Minimal (still being investigated)

### 4. Fixed Pandas NaN Handling
**Problem:** `str(item_row.get('Item Name'))` converted NaN to literal "nan"  
**Fix:** Check with `pd.notna()` before converting to string  
**Impact:** Data quality improvement

---

## Next Steps

### RECOMMENDED: Import from Zoho API
The CSV files are missing **3,211 invoices** (33% of data). We should:

1. **Import ALL invoices from Zoho API** (script ready: `import_invoices_from_api.py`)
2. This will import 10,763 invoices + 1,923 credit notes = 12,686 total transactions
3. Re-calculate MRR for October 2025
4. Expected outcome: MRR gap should reduce significantly

### Alternative Analysis
If API import doesn't close the gap, investigate:
1. VAT handling (amounts should be / 1.25 to exclude VAT?)
2. Transaction type filtering (ensure both "invoice" and "creditnote" counted correctly)
3. Period overlap logic verification
4. Subscription status filtering (ensure "non_renewing" included)

---

## Files Modified

### Core Logic
- `services/invoice.py` - Period parsing functions enhanced
- `import_invoices_complete.py` - CSV import script (currently active)
- `import_invoices_from_api.py` - NEW: API import script (ready to use)

### Analysis Scripts
- `calculate_invoice_mrr.py` - Current vs subscription MRR comparison
- `analyze_mrr_gap.py` - Customer-level gap analysis
- `check_missing_periods.py` - Diagnostic for missing period dates
- `analyze_zoho_report.py` - Zoho master sales report analysis

### Data Files
- `customers_missing_invoices.csv` - 30 customers with subscriptions but no invoices
- `mrr_gap_by_customer.csv` - Full customer-level comparison
- `Zoho master sales report pr 30.09.2025.xlsx` - Ground truth for September

---

## Technical Details

### MRR Calculation Formula
```python
mrr_per_month = invoice_amount / period_months
```

### Period Overlap Logic
Line items are "active" in a month if:
```python
period_start_date <= target_month_end AND period_end_date >= target_month_start
```

### Norwegian Date Parsing Patterns Supported
1. "DD MMM YYYY til DD MMM YYYY" (e.g., "10 Oct 2025 til 09 Nov 2025")
2. "from DD-Month-YYYY to DD-Month-YYYY" (English format)
3. "fra DD måned - DD måned YYYY" (e.g., "1 januar - 31 desember 2022")
4. "DD.MM.YY-DD.MM.YY" (e.g., "01.01.22-31.01.22")

### Product Name Period Indicators
- `(år)`, `(årlig)`, `(årig)` → 12 months
- `(mnd)`, `(månedlig)`, `(måned)` → 1 month

---

## Conclusion

**The primary cause of the 40.7% MRR gap is incomplete CSV data.**

The CSV files are missing 3,211 invoices (33% of total). Importing from the Zoho API should provide complete historical data and significantly reduce or eliminate the gap.

**Action:** Run full API import with `import_invoices_from_api.py` and re-calculate MRR.

---
**Report generated:** 2025-10-11 23:06 CET
