# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SaaS analytics application that fetches subscription data from Zoho Billing API, calculates key metrics (MRR/Churn/NRR/ARPU), and generates natural language insights using ChatGPT.

## Architecture

**Backend**: FastAPI application with async SQLAlchemy
- `services/zoho.py` - OAuth2 integration with Zoho Billing API
- `services/metrics.py` - MRR/Churn/NRR/ARPU calculations using pandas
- `services/analysis.py` - OpenAI integration for generating insights in Norwegian business language
- `models/` - SQLAlchemy models for subscriptions and metrics
- `app.py` - Main FastAPI application entry point

**Data Flow**:
1. Zoho Billing API (OAuth2) → Backend
2. Backend processes with pandas → Calculate metrics
3. Metrics → OpenAI → Natural language analysis
4. Results stored in DB (SQLite/Postgres)
5. Frontend retrieves JSON/HTML from FastAPI endpoints

**Database**: SQLite (dev) or Postgres (production), configured via `DATABASE_URL` env var

## Environment Setup

Required `.env` file variables:
```ini
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_ORG_ID=...
ZOHO_BASE=https://www.zohoapis.eu

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini

APP_ENV=dev
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# Authentication (Optional - leave empty to disable)
AUTH_USERNAME=admin
AUTH_PASSWORD=your_secure_password_here
```

## Development Commands

**Setup**:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -U pip
pip install fastapi uvicorn[standard] httpx python-dotenv pydantic-settings pydantic pandas sqlalchemy aiosqlite openai jinja2
```

**Run Development Server**:
```bash
uvicorn app:app --reload
# Access at http://127.0.0.1:8000
```

**Deployment Options**:
- Desktop shortcut via `.bat` file (see `start_app.bat`)
- Network server: `uvicorn app:app --host 0.0.0.0 --port 8000`
- Standalone executable: `pyinstaller --onefile --noconsole app.py`

## Key API Endpoints

**Homepage & Dashboard**:
- `GET /` - Homepage with sync button
- `GET /api/dashboard` - Main dashboard with metrics and AI analysis
- `GET /api/trends` - Monthly trends view (uses saved snapshots)
- `GET /api/mrr-breakdown-page` - Detailed MRR calculation breakdown

**API Endpoints**:
- `POST /api/sync` - Sync subscriptions from Zoho (automatically saves monthly snapshot)
- `GET /api/metrics` - Calculate current metrics and generate AI analysis
- `GET /api/monthly-trends?months=12&use_snapshots=true` - Get month-over-month trends from snapshots
- `POST /api/generate-historical-snapshots?months_back=12` - Generate snapshots for past months
- `GET /api/debug-mrr` - Debug endpoint to show detailed MRR calculation

## Key Implementation Notes

- OAuth2 token refresh logic for Zoho must handle EU region endpoints
- Analysis prompts in `services/analysis.py` are tuned for Norwegian business terminology
- Metrics calculations assume monthly subscription data structure from Zoho
- Frontend can be JSON API or Jinja2 templates depending on endpoint
- **Incremental Sync**: The system tracks sync history in `SyncStatus` table and only fetches modified subscriptions on subsequent syncs
- **Zoho API Field Mapping**: Note that Zoho sends `interval` as number (e.g., 1) and `interval_unit` as text (e.g., "months"), which is opposite of the field names
- **MRR Normalization**: Yearly subscriptions are divided by 12, multi-month subscriptions are divided by interval_unit
- **⚠️ CRITICAL - VAT Handling**: Zoho stores subscription amounts **INCLUSIVE** of 25% Norwegian VAT (MVA), but their MRR reports show amounts **EXCLUSIVE** of VAT. All MRR calculations must divide amounts by 1.25 to match Zoho's reporting. Formula: `MRR = (amount ÷ 1.25) ÷ interval_months`
- **⚠️ CRITICAL - Subscription Status**: MRR calculations must include both `"live"` AND `"non_renewing"` status subscriptions. Non-renewing subscriptions are still active and generating revenue, they just won't auto-renew at the end of their term.
- **Monthly Snapshots**: The system saves monthly MRR snapshots automatically during each sync. This provides accurate historical data. For the first time setup, use `/api/generate-historical-snapshots` to create past 12 months of snapshots.

## ⚠️ CRITICAL UNDERSTANDING - Two Different MRR Calculation Methods

**This system uses TWO different methods for calculating MRR, and they often give DIFFERENT results. Both are valid but serve different purposes:**

### 1. Subscription-based MRR (from Zoho Subscriptions)
- **Source**: Calculated from active subscriptions in Zoho Subscriptions
- **Used by**: Zoho for their internal calculations
- **Logic**: Based on subscription status (live, non_renewing)
- **Data location**: `subscriptions` table, `monthly_mrr_snapshots` table
- **API endpoints**: `/api/dashboard`, `/api/trends`, `/api/drilldown/mrr`
- **Reference**: "Subscription-baserte tall" or "fra Zoho Subscriptions"

### 2. Invoice-based MRR (from Zoho Billing)
- **Source**: Calculated from actual invoice line items sent to customers
- **Used by**: The accounting department as the basis for MRR reporting
- **Logic**: Based on invoice periods (period_start_date, period_end_date)
- **Data location**: `invoices` table, `invoice_line_items` table, `invoice_mrr_snapshots` table
- **API endpoints**: `/api/invoices/dashboard`, `/api/invoices/trends`
- **Reference**: "Faktura-baserte tall" or "fra Zoho Billing"
- **Status**: Currently in BETA

### Why Are They Different?

The two methods often show different values because:
- Subscriptions may be created but not yet invoiced
- Invoice periods may differ from subscription periods
- One-time charges or adjustments in invoices
- Timing differences between subscription activation and first invoice

**IMPORTANT**: When working with MRR data:
- Always specify which method you're referring to
- Don't assume they should match
- Both are valid - subscription-based follows subscription logic, invoice-based follows accounting reality
- The AI assistant (Niko) has been trained to understand and explain these differences

## ⚠️ CRITICAL - Credit Note Period Handling

**PROBLEM DISCOVERED (Oct 2025)**: Credit notes were initially treated as "point dates" (start_date = end_date = credit_note_date), which caused them to NOT affect MRR calculations for future months.

**Example**:
- Invoice 2008930 issued 2025-01-01 for "Fangstdagbok (år)" = 12 months period (affects Jan 2025 - Jan 2026)
- Credit Note CN-01802 issued 2025-01-21 to cancel this invoice
- ❌ **WRONG**: If credit note has point date (2025-01-21), it ONLY affects January 2025
- ✅ **CORRECT**: Credit note must have SAME period as the product (12 months from 2025-01-21 to 2026-01-20)

**SOLUTION IMPLEMENTED**:
```python
# In import_invoices_xlsx.py lines 96-112:
# Credit notes get periods based on Item Name + periodization from parameters.xlsx
for idx, row in cn_df.iterrows():
    item_name = str(row.get('Item Name', '')).strip()
    cn_date = row['Invoice Date']

    if item_name in periodization_map:
        period_months = periodization_map[item_name]
        # Start from credit note date, extend forward by period_months
        start_date = pd.to_datetime(cn_date)
        end_date = start_date + pd.DateOffset(months=period_months) - pd.DateOffset(days=1)
        cn_df.at[idx, 'Start Date'] = start_date
        cn_df.at[idx, 'End Date'] = end_date
```

**IMPACT**:
- Before fix: MRR gap was +7.9% (invoice MRR too high by 162,000 NOK)
- After fix: MRR gap is -2.7% (within normal range, only 56,662 NOK difference)
- Credit notes reduced Invoice MRR by **218,687 NOK** when periods were corrected!

**KEY RULE**: Credit notes must ALWAYS have the SAME period logic as invoices. If an invoice covers 12 months, its credit note must also cover 12 months (from credit note date forward).

## ⚠️ CRITICAL - Vessel/Call Sign Matching for MRR Gap Analysis

**PROBLEM**: The `subscription_id` field in invoice XLSX files is often empty or doesn't match the actual subscription ID from Zoho API. This made it impossible to match invoices to subscriptions, showing 100% of subscriptions as "unmatched".

**SOLUTION**: Multi-tier matching strategy using vessel data:

**Tier 1 - Subscription ID** (Primary):
- Match by `subscription_id` field when available
- Problem: Often empty in XLSX files (0% match rate in our data)

**Tier 2 - Call Sign** (Secondary, most effective):
- Match by `call_sign` (Radiokallesignal / CF.RKAL)
- Both subscriptions and invoices have this field
- **Success rate: 99.5%** (1,925 out of 1,932 subscriptions matched)
- Implementation: Clean and uppercase call signs for comparison

**Tier 3 - Vessel + Customer** (Tertiary):
- Match by combination of `vessel_name` + `customer_name`
- Used as fallback when call sign doesn't match
- Catches edge cases with typos or formatting differences

**Data Fields Required**:
- Subscriptions: `vessel_name`, `call_sign` (from Zoho custom fields)
- Invoices: `CF.Fartøy`, `CF.Radiokallesignal` (from XLSX files)
- Both indexed in database for fast lookups

**Code Location**: `analyze_mrr_gap.py` lines 35-92, 171-243

**RESULTS**:
- Before vessel matching: 100% subscriptions unmatched (2,060,698 NOK unexplained gap)
- After vessel matching: 99.7% subscriptions matched (only 3,210 NOK from 5 subscriptions unmatched)
- Final gap after all fixes: -2.7% (-56,662 NOK) which is within acceptable range

**KEY RULE**: Always use vessel/call sign as primary matching strategy for Norwegian fishing vessels. The subscription_id field is unreliable in XLSX exports.

## Debug and Troubleshooting

**Check MRR Calculation**:
1. Visit `/api/debug-mrr` and check console output
2. Verify that `interval` and `interval_unit` are correctly mapped
3. Check if amounts include VAT (25% in Norway)

**Check Monthly Trends**:
- Visit `/api/trends` to see historical MRR, customer counts, churn, and net MRR month-over-month

**Force Full Sync**:
- Add `?force_full=true` to sync endpoint: `POST /api/sync?force_full=true`

## Recent Updates (2025-10)

### Version 2.2.0 - MRR Gap Analysis & Credit Note Fix (Oct 2025)
- ✅ **CRITICAL FIX - Credit Note Periods**: Credit notes now get proper period dates (start + period_months) instead of point dates
  - Impact: Reduced MRR gap from +7.9% to -2.7% (fixed 218,687 NOK discrepancy)
  - Credit notes now correctly affect MRR for all months in their period
- ✅ **Vessel/Call Sign Matching**: Implemented multi-tier matching strategy for subscription-invoice reconciliation
  - Tier 1: subscription_id (primary, but often empty)
  - Tier 2: call_sign matching (99.5% success rate - 1,925/1,932 subscriptions matched)
  - Tier 3: vessel_name + customer_name (catches edge cases)
- ✅ **Database Schema Updates**: Added `vessel_name` and `call_sign` columns to `invoice_line_items` table
- ✅ **Analysis Scripts**: Created `analyze_mrr_gap.py`, `check_name_mismatches.py`, `export_mrr_details.py`
- ✅ **Final Result**: MRR gap reduced to acceptable -2.7% (within normal timing differences)

### Version 2.1.0 - Niko AI Churn Analysis Improvements
- ✅ **Complete Churn Data Access**: Niko now has access to ALL churned customers (removed .limit(100))
- ✅ **Extended Historical View**: Shows churn details for last 12 months (up from 6)
- ✅ **More Details Per Month**: Displays up to 20 customers per month with full details
- ✅ **Enhanced AI Instructions**: Niko now ALWAYS includes specific customer names, amounts, and churn reasons
- ✅ **Improved Churn Context**: Automatically groups churn by month with totals and reasons
- ✅ **New Changelog**: Added CHANGELOG.md for version tracking and user communication

### Version 2.0.0 - Major Feature Release
- ✅ **Fixed Sidebar Navigation**: Added permanent left sidebar menu (240px) to all pages
- ✅ **Sortable Tables**: Click column headers to sort customer data
- ✅ **Customer Overview Page**: New "Kunder og oppsigelser" page with complete customer list
- ✅ **Vessel & Call Sign Columns**: Added fartøy and kallesignal data to customer tables
- ✅ **MRR Trend Graph**: Added Chart.js line graph showing monthly MRR trends
- ✅ **Churn Display**: Churned MRR values display in red with minus signs
- ✅ **"Spør Niko" Branding**: Replaced all "AI" references with "Niko"

### Authentication
- ✅ **Basic Auth Implementation**: Added HTTP Basic Authentication to protect all `/api/*` routes
  - Middleware in `app.py` checks credentials for all dashboard/API access
  - Configured via `AUTH_USERNAME` and `AUTH_PASSWORD` environment variables
  - **Optional**: Leave credentials empty to disable auth (not recommended for production)
  - See `AUTH.md` for full setup guide

### Deployment Ready
- ✅ **Prepared for Railway/Render**:
  - `requirements.txt` - All Python dependencies
  - `Procfile` - Deployment command
  - `.env.example` - Template for environment variables
  - `DEPLOYMENT.md` - Complete deployment guide
  - `.gitignore` - Excludes sensitive files (.env, database, etc.)
- ✅ **GitHub Ready**: Code pushed to https://github.com/NikolaiAspen/SaaS-Analytics

### Railway Deployment Notes
**Issue**: Private GitHub repositories require additional access configuration
**Solutions**:
1. **Make repo public** (recommended for internal dashboards):
   - Go to GitHub repo settings → Danger Zone → Change visibility → Make public
   - Safe because `.env` with secrets is gitignored
   - Auth protects actual app access
2. **Grant Railway access to private repos**:
   - GitHub Settings → Installations → Railway → Configure
   - Select "SaaS-Analytics" repository
   - Save and refresh Railway

**Required Environment Variables for Production**:
```
OPENAI_API_KEY=your_openai_key
AUTH_USERNAME=admin
AUTH_PASSWORD=your_secure_password
DATABASE_URL=postgresql://... (auto-set by Railway/Render when adding PostgreSQL)
```

### Files Added
- `auth.py` - Basic authentication module
- `AUTH.md` - Authentication setup guide
- `DEPLOYMENT.md` - Complete deployment instructions
- `Procfile` - Railway/Heroku deployment config
- `.env.example` - Environment variable template
