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
