from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
# Reload: database column added to data/app.db

from config import settings
from database import init_db, get_session
from services import ZohoClient, MetricsCalculator, AnalysisService, ZohoReportImporter, InvoiceService
from models.subscription import Subscription, MetricsSnapshot, SyncStatus, MonthlyMRRSnapshot
from models.invoice import Invoice, InvoiceLineItem, InvoiceMRRSnapshot
from auth import verify_credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="SaaS Analytics",
    description="MRR/Churn analysis from Zoho Billing with Niko insights",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="templates")


# Authentication middleware for all /api/* routes
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Require Basic Auth for all /api/* routes if credentials are configured"""
    # Only protect /api/* routes
    if request.url.path.startswith("/api/"):
        # Check if auth is configured
        if settings.auth_username and settings.auth_password:
            # Verify credentials
            from auth import verify_credentials
            from fastapi.security import HTTPBasic, HTTPBasicCredentials
            import base64

            # Get Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Basic "):
                from fastapi.responses import Response
                return Response(
                    content="Authentication required",
                    status_code=401,
                    headers={"WWW-Authenticate": "Basic realm=\"SaaS Analytics\""}
                )

            # Decode credentials
            try:
                credentials_b64 = auth_header.split(" ")[1]
                credentials_str = base64.b64decode(credentials_b64).decode("utf-8")
                username, password = credentials_str.split(":", 1)

                # Verify
                import secrets
                username_correct = secrets.compare_digest(username, settings.auth_username)
                password_correct = secrets.compare_digest(password, settings.auth_password)

                if not (username_correct and password_correct):
                    from fastapi.responses import Response
                    return Response(
                        content="Invalid credentials",
                        status_code=401,
                        headers={"WWW-Authenticate": "Basic realm=\"SaaS Analytics\""}
                    )
            except Exception:
                from fastapi.responses import Response
                return Response(
                    content="Invalid authentication",
                    status_code=401,
                    headers={"WWW-Authenticate": "Basic realm=\"SaaS Analytics\""}
                )

    response = await call_next(request)
    return response


def get_zoho_client() -> ZohoClient:
    """Dependency for Zoho client"""
    return ZohoClient(
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        refresh_token=settings.zoho_refresh_token,
        org_id=settings.zoho_org_id,
        base_url=settings.zoho_base,
    )


def get_analysis_service() -> AnalysisService:
    """Dependency for analysis service"""
    return AnalysisService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: AsyncSession = Depends(get_session)):
    """Homepage - redirect to dashboard"""
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/api/dashboard", status_code=302)


@app.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    """Import page (old homepage)"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/sync")
async def sync_subscriptions(
    zoho: ZohoClient = Depends(get_zoho_client),
    session: AsyncSession = Depends(get_session),
    force_full: bool = False,
):
    """
    Sync subscriptions from Zoho Billing to local database

    Args:
        force_full: If True, perform a full sync regardless of last sync time
    """
    try:
        # Get last successful sync time
        last_modified_time = None
        if not force_full:
            from sqlalchemy import select, desc
            stmt = select(SyncStatus).where(SyncStatus.success == True).order_by(desc(SyncStatus.last_sync_time)).limit(1)
            result = await session.execute(stmt)
            last_sync = result.scalar_one_or_none()

            if last_sync:
                # Format as ISO string for Zoho API
                last_modified_time = last_sync.last_sync_time.strftime("%Y-%m-%dT%H:%M:%S")
                print(f"Performing incremental sync since {last_modified_time}")
            else:
                print("No previous sync found, performing full sync")
        else:
            print("Force full sync requested")

        # Fetch subscriptions from Zoho (all statuses, including cancelled, to get accurate historical data)
        # Note: We don't filter by status so we can track cancelled subscriptions for accurate churn
        zoho_subs = await zoho.get_all_subscriptions(last_modified_time=last_modified_time)

        synced_count = 0

        # Log first subscription to see all available fields
        if len(zoho_subs) > 0:
            print("\n=== SAMPLE ZOHO SUBSCRIPTION (first sub) ===")
            import json
            print(json.dumps(zoho_subs[0], indent=2))
            print("=" * 80 + "\n")

        for sub_data in zoho_subs:
            # Parse dates with better error handling
            def parse_date(date_value):
                if not date_value:
                    return None
                try:
                    # If already a datetime object (from Zoho API), just strip timezone
                    if isinstance(date_value, datetime):
                        return date_value.replace(tzinfo=None)

                    # Handle string formats from Zoho
                    date_str = str(date_value).strip()
                    if "T" in date_str:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        # Remove timezone info for PostgreSQL compatibility
                        return dt.replace(tzinfo=None)
                    else:
                        # Try parsing as date only
                        from dateutil import parser
                        dt = parser.parse(date_str)
                        # Remove timezone info for PostgreSQL compatibility
                        return dt.replace(tzinfo=None)
                except Exception as e:
                    print(f"Warning: Failed to parse date '{date_value}': {e}")
                    return None

            created_time = parse_date(sub_data.get("created_time"))
            activated_at = parse_date(sub_data.get("activated_at"))
            cancelled_at = parse_date(sub_data.get("cancelled_at"))
            expires_at = parse_date(sub_data.get("expires_at"))

            # For non_renewing subscriptions, use scheduled_cancellation_date as expiry date
            if sub_data.get("status") == "non_renewing":
                scd_raw = sub_data.get("scheduled_cancellation_date")
                print(f"DEBUG: Found non_renewing: {sub_data.get('customer_name')}, raw scd: '{scd_raw}'")
                scheduled_cancellation = parse_date(scd_raw)
                if scheduled_cancellation:
                    expires_at = scheduled_cancellation
                    print(f"  ✓ expires_at set to: {expires_at}")
                else:
                    print(f"  ✗ parse_date returned None")

            # Extract custom fields (vessel and call sign)
            vessel_name = None
            call_sign = None
            custom_fields = sub_data.get("custom_fields", [])
            for field in custom_fields:
                label = field.get("label", "")
                if label == "Fartøy" or field.get("customfield_id") == "Fartøy":
                    vessel_name = field.get("value")
                elif label in ["Kallesignal", "Radiokallesignal"] or field.get("customfield_id") in ["Kallesignal", "Radiokallesignal"]:
                    call_sign = field.get("value")

            # Create or update subscription
            subscription = await session.get(Subscription, sub_data["subscription_id"])

            if subscription:
                # Update existing
                subscription.customer_id = sub_data.get("customer_id", "")
                subscription.customer_name = sub_data.get("customer_name", "")
                subscription.plan_code = sub_data.get("plan_code", "")
                subscription.plan_name = sub_data.get("plan_name", "")
                subscription.status = sub_data.get("status", "")
                subscription.amount = float(sub_data.get("amount", 0))
                subscription.currency_code = sub_data.get("currency_code", "NOK")
                # Note: Zoho sends interval as number and interval_unit as text (e.g. "months", "years")
                subscription.interval = sub_data.get("interval_unit", "months")  # "months" or "years"
                subscription.interval_unit = int(sub_data.get("interval", 1))  # 1, 2, 3, etc.
                subscription.vessel_name = vessel_name
                subscription.call_sign = call_sign
                subscription.created_time = created_time
                subscription.activated_at = activated_at
                subscription.cancelled_at = cancelled_at
                subscription.expires_at = expires_at
                subscription.last_synced = datetime.utcnow()
            else:
                # Create new
                subscription = Subscription(
                    id=sub_data["subscription_id"],
                    customer_id=sub_data.get("customer_id", ""),
                    customer_name=sub_data.get("customer_name", ""),
                    plan_code=sub_data.get("plan_code", ""),
                    plan_name=sub_data.get("plan_name", ""),
                    status=sub_data.get("status", ""),
                    amount=float(sub_data.get("amount", 0)),
                    currency_code=sub_data.get("currency_code", "NOK"),
                    # Note: Zoho sends interval as number and interval_unit as text (e.g. "months", "years")
                    interval=sub_data.get("interval_unit", "months"),  # "months" or "years"
                    interval_unit=int(sub_data.get("interval", 1)),  # 1, 2, 3, etc.
                    vessel_name=vessel_name,
                    call_sign=call_sign,
                    created_time=created_time,
                    activated_at=activated_at,
                    cancelled_at=cancelled_at,
                    expires_at=expires_at,
                )
                session.add(subscription)

            synced_count += 1

        # Save sync status
        sync_status = SyncStatus(
            last_sync_time=datetime.utcnow(),
            subscriptions_synced=synced_count,
            success=True,
        )
        session.add(sync_status)

        await session.commit()

        # Automatically generate historical snapshots on full sync
        calculator = MetricsCalculator(session)

        if not last_modified_time:  # Full sync
            print("\n=== Generating historical snapshots ===")
            from dateutil.relativedelta import relativedelta

            today = datetime.utcnow()
            snapshots_created = []

            # Generate snapshots for last 12 months
            for i in range(12):
                month_date = today - relativedelta(months=i)
                end_of_month = datetime(month_date.year, month_date.month, 1) + relativedelta(months=1) - relativedelta(days=1)
                end_of_month = end_of_month.replace(hour=23, minute=59, second=59)

                month_str = month_date.strftime("%Y-%m")

                try:
                    await calculator.save_monthly_snapshot(month_str, end_of_month)
                    snapshots_created.append(month_str)
                    print(f"Created snapshot for {month_str}")
                except Exception as e:
                    print(f"Warning: Failed to create snapshot for {month_str}: {e}")

            print(f"Generated {len(snapshots_created)} historical snapshots")
        else:
            # Incremental sync - just update current month
            current_month = datetime.utcnow().strftime("%Y-%m")
            try:
                await calculator.save_monthly_snapshot(current_month, datetime.utcnow())
                print(f"Updated snapshot for {current_month}")
            except Exception as e:
                print(f"Warning: Failed to save monthly snapshot: {e}")

        sync_type = "incremental" if last_modified_time else "full"
        return {
            "status": "success",
            "sync_type": sync_type,
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} subscriptions ({sync_type} sync). Historical snapshots generated.",
        }

    except Exception as e:
        await session.rollback()

        # Save failed sync status
        try:
            sync_status = SyncStatus(
                last_sync_time=datetime.utcnow(),
                subscriptions_synced=0,
                success=False,
                error_message=str(e),
            )
            session.add(sync_status)
            await session.commit()
        except:
            pass  # Don't fail on logging failure

        import traceback
        error_detail = f"Sync failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_detail)  # Print to console for debugging
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.get("/api/metrics")
async def get_metrics(
    session: AsyncSession = Depends(get_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Calculate current metrics and generate Niko analysis
    """
    try:
        calculator = MetricsCalculator(session)

        # Get metrics summary
        metrics = await calculator.get_metrics_summary()

        # Get monthly trends for context
        trends = await calculator.get_monthly_trends_from_snapshots(months=3)

        # Debug: Print metrics before sending to Niko
        print("\n=== METRICS SENT TO NIKO ===")
        print(f"MRR: {metrics['mrr']:,.2f} NOK")
        print(f"Total customers: {metrics['total_customers']}")
        print(f"Active subscriptions: {metrics['active_subscriptions']}")
        print(f"Customer churn rate: {metrics['customer_churn_rate']:.2f}%")
        print("=" * 50 + "\n")

        # Generate Niko analysis with trends context
        analysis_text = await analysis_service.generate_analysis(metrics, trends)

        # Save snapshot to database
        snapshot = MetricsSnapshot(
            snapshot_date=metrics["snapshot_date"],
            mrr=metrics["mrr"],
            arr=metrics["arr"],
            total_customers=metrics["total_customers"],
            active_subscriptions=metrics["active_subscriptions"],
            churned_customers=metrics["churned_customers"],
            churned_mrr=0.0,  # Could be calculated separately
            customer_churn_rate=metrics["customer_churn_rate"],
            revenue_churn_rate=metrics["revenue_churn_rate"],
            new_mrr=metrics["new_mrr"],
            expansion_mrr=0.0,  # Could be calculated separately
            contraction_mrr=0.0,  # Could be calculated separately
            arpu=metrics["arpu"],
            analysis_text=analysis_text,
        )

        session.add(snapshot)
        await session.commit()

        return {
            "status": "success",
            "metrics": metrics,
            "analysis": analysis_text,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}")


@app.get("/api/trends", response_class=HTMLResponse)
async def trends_page(request: Request):
    """
    Monthly trends view
    """
    return templates.TemplateResponse("trends.html", {"request": request})


@app.get("/api/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Dashboard view with metrics
    """
    try:
        calculator = MetricsCalculator(session)
        metrics = await calculator.get_metrics_summary()

        # Check if previous month snapshot is missing (warning to import Excel)
        from dateutil.relativedelta import relativedelta
        from sqlalchemy import select

        today = datetime.utcnow()
        previous_month = (today - relativedelta(months=1)).strftime("%Y-%m")

        # Check if we're in a new month and missing previous month's snapshot
        missing_snapshot_warning = None
        if today.day <= 5:  # Show warning for first 5 days of the month
            stmt_previous = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == previous_month)
            result_previous = await session.execute(stmt_previous)
            previous_snapshot = result_previous.scalar_one_or_none()

            if not previous_snapshot:
                month_name = datetime.strptime(previous_month, "%Y-%m").strftime("%B %Y")
                missing_snapshot_warning = f"⚠️ Husk å importere MRR Details rapport for {month_name}! Gå til hjemmesiden og velg 'Importer MRR Details (Excel)'."

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "metrics": metrics,
                "missing_snapshot_warning": missing_snapshot_warning,
                "active_page": "dashboard",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard failed: {str(e)}")


@app.get("/api/documents", response_class=HTMLResponse)
async def documents_page(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Document overview page - shows all imported Excel files/snapshots
    """
    try:
        from dateutil.relativedelta import relativedelta
        from sqlalchemy import select

        # Get only Excel-imported snapshots (not calculated ones)
        stmt = select(MonthlyMRRSnapshot).where(
            MonthlyMRRSnapshot.source == "excel_import"
        ).order_by(MonthlyMRRSnapshot.month.desc())
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        documents = []
        for snapshot in snapshots:
            month_date = datetime.strptime(snapshot.month, "%Y-%m")
            month_name = month_date.strftime("%B %Y").capitalize()

            documents.append({
                "month": snapshot.month,
                "month_name": month_name,
                "has_snapshot": True,
                "mrr": snapshot.mrr,
                "customers": snapshot.total_customers,
                "subscriptions": snapshot.active_subscriptions,
                "arpu": snapshot.arpu,
                "updated_at": snapshot.updated_at,
            })

        # Check if current month is missing
        today = datetime.utcnow()
        current_month = today.strftime("%Y-%m")
        previous_month = (today - relativedelta(months=1)).strftime("%Y-%m")

        missing_current_month = None
        if today.day <= 5:  # First 5 days of month
            stmt_prev = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == previous_month)
            result_prev = await session.execute(stmt_prev)
            prev_snapshot = result_prev.scalar_one_or_none()

            if not prev_snapshot:
                prev_month_name = datetime.strptime(previous_month, "%Y-%m").strftime("%B %Y")
                missing_current_month = f"Husk å importere MRR Details rapport for {prev_month_name}!"

        return templates.TemplateResponse(
            "documents.html",
            {
                "request": request,
                "documents": documents,
                "missing_current_month": missing_current_month,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Documents page failed: {str(e)}")


@app.get("/api/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    """
    User guide page
    """
    return templates.TemplateResponse("guide.html", {"request": request})


@app.get("/api/debug", response_class=HTMLResponse)
async def debug_page(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Debug/Info page - shows database contents and data sources
    """
    try:
        from sqlalchemy import select, func

        # Get all snapshots
        stmt = select(MonthlyMRRSnapshot).order_by(MonthlyMRRSnapshot.month.desc())
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        # Count by source
        stmt_excel = select(func.count(MonthlyMRRSnapshot.id)).where(MonthlyMRRSnapshot.source == "excel_import")
        excel_count = await session.scalar(stmt_excel) or 0

        stmt_calc = select(func.count(MonthlyMRRSnapshot.id)).where(MonthlyMRRSnapshot.source == "calculated")
        calc_count = await session.scalar(stmt_calc) or 0

        # Get subscription counts
        stmt_total_subs = select(func.count(Subscription.id))
        total_subs = await session.scalar(stmt_total_subs) or 0

        stmt_active_subs = select(func.count(Subscription.id)).where(
            Subscription.status.in_(["live", "non_renewing"])
        )
        active_subs = await session.scalar(stmt_active_subs) or 0

        # Get last sync time
        stmt_sync = select(SyncStatus).order_by(SyncStatus.last_sync_time.desc()).limit(1)
        result_sync = await session.execute(stmt_sync)
        last_sync_obj = result_sync.scalar_one_or_none()
        last_sync = last_sync_obj.last_sync_time.strftime('%d.%m.%Y %H:%M') if last_sync_obj else None

        # Prepare snapshot data
        snapshot_data = []
        for snapshot in snapshots:
            month_date = datetime.strptime(snapshot.month, "%Y-%m")
            snapshot_data.append({
                "month": snapshot.month,
                "month_name": month_date.strftime("%B %Y").capitalize(),
                "source": snapshot.source or "calculated",
                "mrr": snapshot.mrr,
                "arr": snapshot.arr,
                "total_customers": snapshot.total_customers,
                "active_subscriptions": snapshot.active_subscriptions,
                "new_mrr": snapshot.new_mrr,
                "churned_mrr": snapshot.churned_mrr,
                "updated_at": snapshot.updated_at,
            })

        stats = {
            "total_snapshots": len(snapshots),
            "excel_snapshots": excel_count,
            "calculated_snapshots": calc_count,
            "total_subscriptions": total_subs,
            "active_subscriptions": active_subs,
            "last_sync": last_sync,
        }

        return templates.TemplateResponse(
            "debug.html",
            {
                "request": request,
                "snapshots": snapshot_data,
                "stats": stats,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug page failed: {str(e)}")


@app.get("/api/monthly-trends")
async def get_monthly_trends(
    session: AsyncSession = Depends(get_session),
    months: int = 12,
    use_snapshots: bool = True,
):
    """
    Get month-over-month trends

    Args:
        use_snapshots: If True, use saved snapshots (accurate historical data)
                      If False, calculate from current subscription data (may be inaccurate for old months)
    """
    try:
        calculator = MetricsCalculator(session)

        if use_snapshots:
            trends = await calculator.get_monthly_trends_from_snapshots(months=months)
        else:
            trends = await calculator.get_monthly_trends(months=months)

        return {
            "status": "success",
            "trends": trends,
            "data_source": "snapshots" if use_snapshots else "calculated",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trends: {str(e)}")


@app.get("/api/mrr-breakdown-page", response_class=HTMLResponse)
async def mrr_breakdown_page(request: Request):
    """
    MRR breakdown page
    """
    return templates.TemplateResponse("mrr_breakdown.html", {"request": request})


@app.get("/api/mrr-breakdown")
async def get_mrr_breakdown(
    session: AsyncSession = Depends(get_session),
    month: Optional[str] = None,
):
    """
    Get detailed MRR calculation breakdown

    Args:
        month: Optional month in YYYY-MM format (e.g., "2025-01") to show breakdown for that specific month
    """
    try:
        from sqlalchemy import select, func
        from dateutil.relativedelta import relativedelta

        # If month is specified, calculate as of end of that month
        as_of_date = None
        if month:
            year, month_num = map(int, month.split('-'))
            # Calculate end of the specified month
            as_of_date = datetime(year, month_num, 1) + relativedelta(months=1) - relativedelta(days=1)
            as_of_date = as_of_date.replace(hour=23, minute=59, second=59)

            # Get subscriptions that were active at that time
            stmt = select(Subscription).where(
                Subscription.status.in_(["live", "non_renewing", "cancelled"]),
                Subscription.activated_at <= as_of_date,
                (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > as_of_date)
            )
        else:
            # Get all currently live subscriptions (including non_renewing)
            stmt = select(Subscription).where(Subscription.status.in_(["live", "non_renewing"]))

        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        # Calculate summary
        total_mrr = 0
        monthly_mrr = 0
        yearly_mrr = 0
        monthly_count = 0
        yearly_count = 0
        monthly_total = 0
        yearly_total = 0

        top_subs = []

        for sub in subscriptions:
            # Remove 25% Norwegian VAT (MVA) from amount
            amount_without_vat = sub.amount / 1.25

            if sub.interval == "months":
                mrr = amount_without_vat / sub.interval_unit
                monthly_mrr += mrr
                monthly_count += 1
                monthly_total += sub.amount
            elif sub.interval == "years":
                mrr = amount_without_vat / (sub.interval_unit * 12)
                yearly_mrr += mrr
                yearly_count += 1
                yearly_total += sub.amount
            else:
                mrr = amount_without_vat

            total_mrr += mrr
            top_subs.append({
                "customer_name": sub.customer_name,
                "plan_name": sub.plan_name,
                "amount": sub.amount,
                "currency": sub.currency_code,
                "interval": sub.interval,
                "interval_unit": sub.interval_unit,
                "interval_label": f"{sub.interval} ({sub.interval_unit}x)" if sub.interval_unit > 1 else sub.interval,
                "mrr": mrr
            })

        # Sort top subscriptions by MRR
        top_subs.sort(key=lambda x: x["mrr"], reverse=True)

        # Get unique customers
        unique_customers = len(set(sub.customer_id for sub in subscriptions))

        # Get monthly snapshot data if viewing specific month
        snapshot_data = None
        is_excel_import = False
        if month:
            snapshot_stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month)
            snapshot_result = await session.execute(snapshot_stmt)
            snapshot = snapshot_result.scalar_one_or_none()
            if snapshot:
                is_excel_import = (snapshot.source == "excel_import")
                snapshot_data = {
                    "mrr": snapshot.mrr,
                    "arr": snapshot.arr,
                    "total_customers": snapshot.total_customers,
                    "active_subscriptions": snapshot.active_subscriptions,
                    "new_mrr": snapshot.new_mrr,
                    "churned_mrr": snapshot.churned_mrr,
                    "net_mrr": snapshot.net_mrr,
                    "arpu": snapshot.arpu,
                    "source": snapshot.source or "calculated"
                }
                # Use snapshot data for summary when available (more accurate than recalculation)
                summary_data = {
                    "total_mrr": snapshot.mrr,
                    "total_subscriptions": snapshot.active_subscriptions,
                    "total_customers": snapshot.total_customers,
                    "arpu": snapshot.arpu,
                    "data_source": "excel_import" if is_excel_import else "snapshot"
                }

                # If Excel import, don't show individual subscriptions (unreliable for historical data)
                if is_excel_import:
                    top_subs = []
            else:
                # No snapshot available, use calculated data
                summary_data = {
                    "total_mrr": round(total_mrr, 2),
                    "total_subscriptions": len(subscriptions),
                    "total_customers": unique_customers,
                    "arpu": round(total_mrr / unique_customers, 2) if unique_customers > 0 else 0,
                    "data_source": "calculated"  # Indicate this is calculated
                }
        else:
            # Current month - use calculated data
            summary_data = {
                "total_mrr": round(total_mrr, 2),
                "total_subscriptions": len(subscriptions),
                "total_customers": unique_customers,
                "arpu": round(total_mrr / unique_customers, 2) if unique_customers > 0 else 0,
                "data_source": "calculated"
            }

        return {
            "status": "success",
            "month": month,
            "as_of_date": as_of_date.strftime("%Y-%m-%d %H:%M:%S") if as_of_date else None,
            "snapshot": snapshot_data,
            "summary": summary_data,
            "breakdown": [
                {
                    "interval": "months",
                    "interval_label": "Månedlig",
                    "count": monthly_count,
                    "total_amount": round(monthly_total, 2),
                    "mrr": round(monthly_mrr, 2),
                    "percentage": round(monthly_mrr / total_mrr * 100, 2) if total_mrr > 0 else 0,
                },
                {
                    "interval": "years",
                    "interval_label": "Årlig",
                    "count": yearly_count,
                    "total_amount": round(yearly_total, 2),
                    "mrr": round(yearly_mrr, 2),
                    "percentage": round(yearly_mrr / total_mrr * 100, 2) if total_mrr > 0 else 0,
                },
            ],
            "all_subscriptions": top_subs,  # Show all subscriptions (sorted by MRR)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get MRR breakdown: {str(e)}")


class ImportRequest(BaseModel):
    file_path: str
    month: Optional[str] = None  # Optional month override (YYYY-MM)


@app.post("/api/import-zoho-mrr-details")
async def import_zoho_mrr_details(
    request: ImportRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Import Zoho's MRR Details report (subscription-level data) for a specific month
    This is the MOST ACCURATE way to get monthly snapshots - uses Zoho's exact calculations

    Usage:
    1. In Zoho Billing, go to Reports → MRR Insights
    2. Select date range for the month (e.g., 2024-09-01 to 2024-09-30)
    3. Export to Excel
    4. Place file in Downloads folder
    5. Call this endpoint with file path
    """
    try:
        importer = ZohoReportImporter()
        month_data = importer.import_mrr_details_report(request.file_path, request.month)

        # Update or create snapshot with Zoho's exact numbers
        from sqlalchemy import select

        month = month_data['month']
        stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month)
        result = await session.execute(stmt)
        existing_snapshot = result.scalar_one_or_none()

        if existing_snapshot:
            # Update with Zoho's exact numbers
            existing_snapshot.mrr = round(month_data['mrr'], 2)
            existing_snapshot.arr = round(month_data['mrr'] * 12, 2)
            existing_snapshot.total_customers = month_data['customer_count']
            existing_snapshot.active_subscriptions = month_data['subscription_count']
            message = f"Updated snapshot for {month} with Zoho's exact data"
        else:
            # Create new snapshot
            snapshot = MonthlyMRRSnapshot(
                month=month,
                mrr=round(month_data['mrr'], 2),
                arr=round(month_data['mrr'] * 12, 2),
                total_customers=month_data['customer_count'],
                active_subscriptions=month_data['subscription_count'],
                new_mrr=0.0,  # Can be calculated later
                churned_mrr=0.0,  # Can be calculated later
                net_mrr=0.0,  # Can be calculated later
            )
            session.add(snapshot)
            message = f"Created snapshot for {month} with Zoho's exact data"

        await session.commit()

        return {
            "status": "success",
            "message": message,
            "month": month,
            "mrr": month_data['mrr'],
            "customers": month_data['customer_count'],
            "subscriptions": month_data['subscription_count'],
        }

    except Exception as e:
        await session.rollback()
        import traceback
        print(f"Import failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post("/api/import-zoho-mrr-report")
async def import_zoho_mrr_report(
    request: ImportRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Import Zoho's Monthly MRR Excel report to create accurate historical snapshots

    Args:
        request: JSON body with file_path to the Zoho MRR Excel file
    """
    file_path = request.file_path
    try:
        # Import the report
        importer = ZohoReportImporter()
        monthly_data = importer.import_monthly_mrr_report(file_path)

        if not monthly_data:
            raise HTTPException(status_code=400, detail="No data found in the Excel file")

        # Save each month's data as a snapshot
        from sqlalchemy import select

        snapshots_created = []
        snapshots_updated = []

        for month_data in monthly_data:
            month = month_data['month']
            mrr = month_data['mrr']

            # Check if snapshot already exists
            stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month)
            result = await session.execute(stmt)
            existing_snapshot = result.scalar_one_or_none()

            if existing_snapshot:
                # Update MRR with Zoho's actual value
                existing_snapshot.mrr = round(mrr, 2)
                existing_snapshot.arr = round(mrr * 12, 2)
                existing_snapshot.source = "excel_import"  # Mark as from Excel import
                snapshots_updated.append(month)
            else:
                # Create new snapshot with just MRR
                # Other fields will be populated when we calculate them
                snapshot = MonthlyMRRSnapshot(
                    month=month,
                    mrr=round(mrr, 2),
                    arr=round(mrr * 12, 2),
                    total_customers=0,  # Will be calculated later
                    active_subscriptions=0,  # Will be calculated later
                    source="excel_import",  # Mark as from Excel import
                )
                session.add(snapshot)
                snapshots_created.append(month)

        await session.commit()

        return {
            "status": "success",
            "message": f"Imported {len(monthly_data)} months of MRR data from Zoho",
            "snapshots_created": snapshots_created,
            "snapshots_updated": snapshots_updated,
        }

    except Exception as e:
        await session.rollback()
        import traceback
        print(f"Import failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.get("/api/churn-status")
async def get_churn_status(session: AsyncSession = Depends(get_session)):
    """
    Get churn import status for all months
    """
    try:
        from sqlalchemy import select, func
        from models.subscription import ChurnedCustomer
        from dateutil.relativedelta import relativedelta

        # Get last 12 months
        today = datetime.utcnow()
        months = []
        for i in range(12):
            month_date = today - relativedelta(months=i)
            month_str = month_date.strftime("%Y-%m")
            months.append({
                'month': month_str,
                'month_name': month_date.strftime("%B %Y"),
            })

        # Get churn data for each month
        result_months = []
        for month_info in reversed(months):
            month = month_info['month']

            # Get snapshot data using raw SQL to avoid mapper cache issues
            from sqlalchemy import text
            sql = text("""
                SELECT churned_customers, churned_mrr, updated_at
                FROM monthly_mrr_snapshots
                WHERE month = :month
            """)
            result = await session.execute(sql, {'month': month})
            row = result.fetchone()

            # Count unique cancellation reasons
            reason_stmt = select(func.count(func.distinct(ChurnedCustomer.cancellation_reason))).where(
                ChurnedCustomer.month == month,
                ChurnedCustomer.cancellation_reason.isnot(None)
            )
            reason_result = await session.execute(reason_stmt)
            reason_count = reason_result.scalar() or 0

            # Extract values from raw SQL row
            churned_customers = row[0] if row and row[0] is not None else 0
            churned_mrr = row[1] if row and row[1] is not None else 0.0
            updated_at_raw = row[2] if row and row[2] is not None else None

            if row and churned_customers and churned_customers > 0:
                # Parse datetime string from database
                if updated_at_raw:
                    try:
                        from datetime import datetime as dt
                        updated_at_dt = dt.fromisoformat(updated_at_raw.replace(' ', 'T'))
                        updated_at_str = updated_at_dt.strftime('%d.%m.%Y kl. %H:%M')
                    except:
                        updated_at_str = 'N/A'
                else:
                    updated_at_str = 'N/A'
                result_months.append({
                    'month': month,
                    'month_name': month_info['month_name'],
                    'churned_customers': churned_customers,
                    'churned_mrr': churned_mrr,
                    'reason_count': reason_count,
                    'updated_at': updated_at_str,
                })
            else:
                result_months.append({
                    'month': month,
                    'month_name': month_info['month_name'],
                    'churned_customers': 0,
                    'churned_mrr': 0,
                    'reason_count': 0,
                    'updated_at': None,
                })

        return {
            "status": "success",
            "months": result_months,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get churn status: {str(e)}")


@app.post("/api/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload and import Excel file
    """
    import tempfile
    import os

    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Import the MRR Details report (subscription-level data)
        importer = ZohoReportImporter()
        import_result = importer.import_mrr_details_report(tmp_file_path)

        if not import_result:
            raise HTTPException(status_code=400, detail="No data found in the Excel file")

        # Save month's data as a snapshot
        from sqlalchemy import select

        month = import_result['month']
        mrr = import_result['mrr']
        customer_count = import_result['customer_count']
        subscription_count = import_result['subscription_count']
        arpu = import_result['arpu']

        # Check if snapshot already exists
        stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month)
        result = await session.execute(stmt)
        existing_snapshot = result.scalar_one_or_none()

        snapshots_created = []
        snapshots_updated = []

        if existing_snapshot:
            # Update with Zoho's actual values
            existing_snapshot.mrr = round(mrr, 2)
            existing_snapshot.arr = round(mrr * 12, 2)
            existing_snapshot.total_customers = customer_count
            existing_snapshot.active_subscriptions = subscription_count
            existing_snapshot.arpu = round(arpu, 2)
            existing_snapshot.source = "excel_import"  # Mark as from Excel import
            snapshots_updated.append(month)
        else:
            # Create new snapshot with all data
            snapshot = MonthlyMRRSnapshot(
                month=month,
                mrr=round(mrr, 2),
                arr=round(mrr * 12, 2),
                total_customers=customer_count,
                active_subscriptions=subscription_count,
                arpu=round(arpu, 2),
                new_mrr=0.0,  # Will be calculated later if needed
                churned_mrr=0.0,  # Will be calculated later if needed
                net_mrr=0.0,  # Will be calculated later if needed
                source="excel_import",  # Mark as from Excel import
            )
            session.add(snapshot)
            snapshots_created.append(month)

        await session.commit()

        # Clean up temp file
        os.unlink(tmp_file_path)

        return {
            "status": "success",
            "message": f"Imported {month} - MRR: {mrr:,.0f} kr ({subscription_count} subs, {customer_count} customers)",
            "snapshots_created": snapshots_created,
            "snapshots_updated": snapshots_updated,
        }

    except Exception as e:
        await session.rollback()
        # Clean up temp file if it exists
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        import traceback
        print(f"Upload failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/upload-churn")
async def upload_churn(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Upload and import Churn report Excel file
    """
    import tempfile
    import os

    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Import the Churn report - pass original filename for month extraction
        importer = ZohoReportImporter()

        # Try to extract month from original filename first
        original_filename = file.filename
        month_from_filename = None
        if original_filename:
            import re
            month_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(\d{2})', original_filename.lower())
            if month_match:
                month_name = month_match.group(1)
                year = f"20{month_match.group(2)}"
                month_map = {
                    'january': '01', 'jan': '01',
                    'february': '02', 'feb': '02',
                    'march': '03', 'mar': '03',
                    'april': '04', 'apr': '04',
                    'may': '05',
                    'june': '06', 'jun': '06',
                    'july': '07', 'jul': '07',
                    'august': '08', 'aug': '08',
                    'september': '09', 'sep': '09', 'sept': '09',
                    'october': '10', 'oct': '10',
                    'november': '11', 'nov': '11',
                    'december': '12', 'dec': '12'
                }
                month_from_filename = f"{year}-{month_map[month_name]}"

        churn_result = importer.import_churn_report(tmp_file_path, month=month_from_filename)

        if not churn_result:
            raise HTTPException(status_code=400, detail="No churn data found in the Excel file")

        from sqlalchemy import select

        month = churn_result['month']
        churned_customers = churn_result['churned_customers']
        churned_mrr = churn_result['churned_mrr']
        churn_details = churn_result.get('churn_details', [])

        # Find existing snapshot for this month
        stmt = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month)
        result = await session.execute(stmt)
        existing_snapshot = result.scalar_one_or_none()

        if existing_snapshot:
            # Update churn data
            existing_snapshot.churned_customers = churned_customers
            existing_snapshot.churned_mrr = round(churned_mrr, 2)
            # Recalculate net MRR if we have new_mrr
            if existing_snapshot.new_mrr:
                existing_snapshot.net_mrr = round(existing_snapshot.new_mrr - churned_mrr, 2)
            message = f"Updated churn data for {month}"
        else:
            # Create new snapshot with only churn data (MRR will be added later)
            snapshot = MonthlyMRRSnapshot(
                month=month,
                mrr=0.0,  # Will be updated when MRR Details is imported
                arr=0.0,
                total_customers=0,
                active_subscriptions=0,
                arpu=0.0,
                new_mrr=0.0,
                churned_customers=churned_customers,
                churned_mrr=round(churned_mrr, 2),
                net_mrr=round(-churned_mrr, 2),  # Negative since we only have churn
                source="partial",  # Mark as partial until MRR Details is imported
            )
            session.add(snapshot)
            message = f"Created partial snapshot for {month} with churn data"

        # Delete existing churn details for this month (to avoid duplicates)
        from models.subscription import ChurnedCustomer
        delete_stmt = select(ChurnedCustomer).where(ChurnedCustomer.month == month)
        delete_result = await session.execute(delete_stmt)
        existing_records = delete_result.scalars().all()
        for record in existing_records:
            await session.delete(record)

        # Save detailed churn records
        for detail in churn_details:
            churn_record = ChurnedCustomer(
                month=month,
                customer_id=detail['customer_id'],
                customer_name=detail['customer_name'],
                customer_email=detail['customer_email'],
                subscription_id=detail['subscription_id'],
                plan_name=detail['plan_name'],
                amount=detail['amount'],
                cancellation_reason=detail['cancellation_reason'],
                cancelled_date=detail['cancelled_date'],
                ltv=detail['ltv'],
                ltd=detail['ltd'],
            )
            session.add(churn_record)

        await session.commit()

        # Clean up temp file
        os.unlink(tmp_file_path)

        return {
            "status": "success",
            "message": f"{message} - {churned_customers} churned customers, {churned_mrr:,.2f} kr churned MRR",
            "month": month,
            "churned_customers": churned_customers,
            "churned_mrr": churned_mrr,
        }

    except Exception as e:
        await session.rollback()
        # Clean up temp file if it exists
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        import traceback
        print(f"Churn upload failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Churn upload failed: {str(e)}")


class QuestionRequest(BaseModel):
    question: str


@app.post("/api/ask-ai")
async def ask_ai_question(
    request: QuestionRequest,
    session: AsyncSession = Depends(get_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Ask Niko a question about the metrics data
    """
    try:
        calculator = MetricsCalculator(session)

        # Get current metrics
        metrics = await calculator.get_metrics_summary()

        # Get recent trends
        trends = await calculator.get_monthly_trends_from_snapshots(months=6)

        # Get answer from Niko
        answer = await analysis_service.ask_question(request.question, metrics, trends)

        return {
            "status": "success",
            "question": request.question,
            "answer": answer,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")


@app.post("/api/ask-trends")
async def ask_trends_question(
    request: QuestionRequest,
    session: AsyncSession = Depends(get_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Ask Niko about trends, changes, churn - focused on Excel snapshot data
    """
    try:
        calculator = MetricsCalculator(session)

        # Get 12 months of trends from snapshots (Excel data)
        trends = await calculator.get_monthly_trends_from_snapshots(months=12)

        # Get churn details with cancellation reasons for context
        from models.subscription import ChurnedCustomer
        from sqlalchemy import select

        # Build detailed context focused on trends and changes
        context = "Her er de månedlige trendene basert på importerte Excel-filer fra Zoho:\n\n"

        for trend in trends:
            context += f"**{trend['month_name']}:**\n"
            context += f"  - MRR: {trend['mrr']:,.0f} kr"

            if trend.get('mrr_change'):
                change_sign = "+" if trend['mrr_change'] > 0 else ""
                context += f" ({change_sign}{trend['mrr_change']:,.0f} kr, {trend.get('mrr_change_pct', 0):+.1f}%)"

            context += f"\n  - Kunder: {trend['customers']}"

            if trend.get('customer_change'):
                change_sign = "+" if trend['customer_change'] > 0 else ""
                context += f" ({change_sign}{trend['customer_change']})"

            context += f"\n  - Abonnementer: {trend['subscriptions']}"
            context += f"\n  - Ny MRR: {trend.get('new_mrr', 0):,.0f} kr"
            context += f"\n  - Churned MRR: {trend.get('churned_mrr', 0):,.0f} kr"
            context += f"\n  - Net MRR: {trend.get('net_mrr', 0):+,.0f} kr"
            context += f"\n  - Churned kunder: {trend.get('churned_customers', 0)}"

            # Add cancellation reasons if available
            if trend.get('churned_customers', 0) > 0:
                churn_stmt = select(ChurnedCustomer).where(ChurnedCustomer.month == trend['month'])
                churn_result = await session.execute(churn_stmt)
                churned_records = churn_result.scalars().all()

                if churned_records:
                    # Group by reason
                    reasons = {}
                    for record in churned_records:
                        reason = record.cancellation_reason or "Ukjent årsak"
                        if reason not in reasons:
                            reasons[reason] = {'count': 0, 'mrr': 0}
                        reasons[reason]['count'] += 1
                        reasons[reason]['mrr'] += record.amount

                    context += "\n  - **Churn-årsaker:**"
                    for reason, data in sorted(reasons.items(), key=lambda x: x[1]['mrr'], reverse=True):
                        context += f"\n    • {reason}: {data['count']} kunder ({data['mrr']:,.0f} kr MRR)"

            context += "\n\n"

        # Ask Niko with focus on trends and why changes occur
        prompt = f"""{context}

VIKTIG: Fokuser på TRENDER og ENDRINGER. Brukeren vil vite:
- HVORFOR endringer skjer (ikke bare HVA som har endret seg)
- Årsaker til MRR-tap eller kundetap
- Mønstre i churn og vekst
- Hvilke måneder som skiller seg ut og hvorfor

Spørsmål fra brukeren: {request.question}

Svar med konkrete innsikter om trender og årsaker til endringer basert på dataene ovenfor."""

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model=analysis_service.model,
            messages=[
                {"role": "system", "content": "Du er en SaaS-analyseekspert som fokuserer på å identifisere trender, forklare endringer i MRR og churn, og finne årsaker til kundetap. Vær konkret og gi innsiktsfulle analyser."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800,
        )

        answer = response.choices[0].message.content

        return {
            "status": "success",
            "question": request.question,
            "answer": answer,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze trends: {str(e)}")


class ComprehensiveQuestionRequest(BaseModel):
    question: str
    conversation_history: list = []


@app.post("/api/ask-niko")
async def ask_niko_comprehensive(
    request: ComprehensiveQuestionRequest,
    session: AsyncSession = Depends(get_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """
    Ask Niko anything - comprehensive endpoint that combines all data sources
    """
    try:
        calculator = MetricsCalculator(session)

        # Get subscription metrics and trends (4 måneder for historisk kontekst)
        subscription_metrics = await calculator.get_metrics_summary()
        subscription_trends = await calculator.get_monthly_trends_from_snapshots(months=4)

        # Get invoice metrics and trends if available
        invoice_metrics = None
        invoice_trends = None
        try:
            from services.invoice import InvoiceService
            invoice_service = InvoiceService(session)

            # Get latest invoice snapshot
            from models.invoice import InvoiceMRRSnapshot
            from sqlalchemy import select
            stmt = select(InvoiceMRRSnapshot).order_by(InvoiceMRRSnapshot.month.desc()).limit(1)
            result = await session.execute(stmt)
            latest_invoice_snapshot = result.scalar_one_or_none()

            if latest_invoice_snapshot:
                invoice_metrics = {
                    'mrr': latest_invoice_snapshot.mrr,
                    'arr': latest_invoice_snapshot.arr,
                    'arpu': latest_invoice_snapshot.arpu,
                    'total_customers': latest_invoice_snapshot.total_customers,
                    'active_invoices': latest_invoice_snapshot.active_invoices,
                }

                # Get invoice trends (kun 3 måneder)
                stmt = select(InvoiceMRRSnapshot).order_by(InvoiceMRRSnapshot.month.desc()).limit(3)
                result = await session.execute(stmt)
                snapshots = result.scalars().all()

                invoice_trends = []
                for i, snapshot in enumerate(snapshots):
                    trend = {
                        'month': snapshot.month,
                        'month_name': snapshot.month,
                        'mrr': snapshot.mrr,
                        'arr': snapshot.arr,
                        'arpu': snapshot.arpu,
                        'customers': snapshot.total_customers,
                    }

                    # Calculate changes
                    if i < len(snapshots) - 1:
                        prev = snapshots[i + 1]
                        trend['mrr_change'] = snapshot.mrr - prev.mrr
                        trend['mrr_change_pct'] = ((snapshot.mrr - prev.mrr) / prev.mrr * 100) if prev.mrr > 0 else 0
                        trend['customer_change'] = snapshot.total_customers - prev.total_customers

                    invoice_trends.append(trend)
        except Exception as e:
            print(f"Could not load invoice data: {e}")

        # Get churn details with subscription info
        churn_details = []
        try:
            from models.subscription import ChurnedCustomer, Subscription
            from sqlalchemy import select

            # Get recent churned customers (kun 5 for korthet)
            stmt = select(ChurnedCustomer).order_by(ChurnedCustomer.cancelled_date.desc()).limit(5)
            result = await session.execute(stmt)
            churned_records = result.scalars().all()

            for record in churned_records:
                churn_details.append({
                    'customer_name': record.customer_name,
                    'amount': record.amount,
                    'reason': record.cancellation_reason,
                    'churned_at': record.cancelled_date.strftime('%Y-%m-%d') if record.cancelled_date else None,
                    'plan_name': record.plan_name if hasattr(record, 'plan_name') else None
                })
        except Exception as e:
            print(f"Could not load churn details: {e}")

        # Get new customer details (siste 5 nye kunder)
        new_customer_details = []
        try:
            from models.subscription import Subscription
            from sqlalchemy import select
            from datetime import datetime, timedelta

            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            stmt = (
                select(Subscription)
                .where(Subscription.activated_at >= thirty_days_ago)
                .where(Subscription.status.in_(['live', 'non_renewing']))
                .order_by(Subscription.activated_at.desc())
                .limit(5)
            )
            result = await session.execute(stmt)
            new_subs = result.scalars().all()

            for sub in new_subs:
                new_customer_details.append({
                    'customer_name': sub.customer_name,
                    'amount': sub.amount,
                    'plan_name': sub.plan_name,
                    'created_at': sub.activated_at.strftime('%Y-%m-%d') if sub.activated_at else None
                })
        except Exception as e:
            print(f"Could not load new customer details: {e}")

        # Ask Niko with full context
        answer = await analysis_service.ask_comprehensive(
            question=request.question,
            subscription_metrics=subscription_metrics,
            subscription_trends=subscription_trends,
            invoice_metrics=invoice_metrics,
            invoice_trends=invoice_trends,
            churn_details=churn_details,
            new_customer_details=new_customer_details,
            conversation_history=request.conversation_history
        )

        return {
            "status": "success",
            "question": request.question,
            "answer": answer,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")


@app.post("/api/generate-historical-snapshots")
async def generate_historical_snapshots(
    session: AsyncSession = Depends(get_session),
    months_back: int = 12,
):
    """
    Generate monthly snapshots for historical months
    This calculates MRR for past months based on current subscription data
    """
    try:
        calculator = MetricsCalculator(session)
        from dateutil.relativedelta import relativedelta

        today = datetime.utcnow()
        snapshots_created = []

        for i in range(months_back):
            # Calculate end of each month
            month_date = today - relativedelta(months=i)
            end_of_month = datetime(month_date.year, month_date.month, 1) + relativedelta(months=1) - relativedelta(days=1)
            end_of_month = end_of_month.replace(hour=23, minute=59, second=59)

            month_str = month_date.strftime("%Y-%m")

            try:
                await calculator.save_monthly_snapshot(month_str, end_of_month)
                snapshots_created.append(month_str)
                print(f"Created snapshot for {month_str}")
            except Exception as e:
                print(f"Failed to create snapshot for {month_str}: {e}")

        return {
            "status": "success",
            "message": f"Generated {len(snapshots_created)} monthly snapshots",
            "snapshots": snapshots_created,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate snapshots: {str(e)}")


@app.get("/api/debug-mrr")
async def debug_mrr(
    session: AsyncSession = Depends(get_session),
):
    """
    Debug endpoint to show detailed MRR calculation
    """
    try:
        calculator = MetricsCalculator(session)

        # This will print debug info to console
        mrr = await calculator.calculate_mrr(debug=True)

        # Also get all subscriptions to return summary
        from sqlalchemy import select
        stmt = select(Subscription).where(Subscription.status == "live")
        result = await session.execute(stmt)
        all_subs = result.scalars().all()

        return {
            "status": "success",
            "message": "Check console for detailed debug output",
            "total_subscriptions": len(all_subs),
            "calculated_mrr": mrr,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clear-snapshots")
async def clear_snapshots(session: AsyncSession = Depends(get_session)):
    """
    Clear all monthly snapshots from database
    """
    try:
        from sqlalchemy import delete

        # Delete all snapshots
        stmt = delete(MonthlyMRRSnapshot)
        result = await session.execute(stmt)
        await session.commit()

        deleted_count = result.rowcount

        return {
            "status": "success",
            "message": f"Slettet {deleted_count} snapshots",
            "deleted": deleted_count,
        }

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Kunne ikke slette snapshots: {str(e)}")


@app.post("/api/clear-subscriptions")
async def clear_subscriptions(session: AsyncSession = Depends(get_session)):
    """
    Clear all subscriptions from database
    """
    try:
        from sqlalchemy import delete

        # Delete all subscriptions
        stmt = delete(Subscription)
        result = await session.execute(stmt)
        await session.commit()

        deleted_count = result.rowcount

        return {
            "status": "success",
            "message": f"Slettet {deleted_count} subscriptions",
            "deleted": deleted_count,
        }

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Kunne ikke slette subscriptions: {str(e)}")


@app.post("/api/clear-all")
async def clear_all(session: AsyncSession = Depends(get_session)):
    """
    Clear entire database (nuclear option)
    """
    try:
        from sqlalchemy import delete

        # Delete everything
        stmt_snapshots = delete(MonthlyMRRSnapshot)
        result_snapshots = await session.execute(stmt_snapshots)

        stmt_subs = delete(Subscription)
        result_subs = await session.execute(stmt_subs)

        stmt_sync = delete(SyncStatus)
        result_sync = await session.execute(stmt_sync)

        stmt_metrics = delete(MetricsSnapshot)
        result_metrics = await session.execute(stmt_metrics)

        await session.commit()

        total_deleted = (
            result_snapshots.rowcount +
            result_subs.rowcount +
            result_sync.rowcount +
            result_metrics.rowcount
        )

        return {
            "status": "success",
            "message": f"Database tømt! Slettet {total_deleted} rader totalt",
            "deleted": {
                "snapshots": result_snapshots.rowcount,
                "subscriptions": result_subs.rowcount,
                "sync_status": result_sync.rowcount,
                "metrics": result_metrics.rowcount,
            },
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Kunne ikke tømme database: {str(e)}")


@app.get("/api/drilldown/customers", response_class=HTMLResponse)
async def drilldown_customers(request: Request, session: AsyncSession = Depends(get_session)):
    """Drilldown: All customers with their subscriptions"""
    try:
        from sqlalchemy import select, func

        # Get all active subscriptions with customer info
        stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"])
        ).order_by(Subscription.customer_name)

        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        # Group by customer
        customers = {}
        for sub in subscriptions:
            if sub.customer_id not in customers:
                customers[sub.customer_id] = {
                    'id': sub.customer_id,
                    'customer_name': sub.customer_name,
                    'subscriptions': [],
                    'total_mrr': 0
                }

            calculator = MetricsCalculator(session)
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)

            customers[sub.customer_id]['subscriptions'].append({
                'subscription_id': sub.id,
                'product_name': sub.plan_name or 'N/A',
                'vessel_name': sub.vessel_name or 'N/A',
                'call_sign': sub.call_sign or 'N/A',
                'amount': f"{sub.amount:,.0f} kr",
                'interval': f"{sub.interval_unit} {sub.interval}",
                'status': sub.status,
                'mrr': f"{mrr:,.0f} kr",
                'activated_at': sub.activated_at.strftime('%d.%m.%Y') if sub.activated_at else 'N/A'
            })
            customers[sub.customer_id]['total_mrr'] += mrr

        # Prepare data for template
        data = []
        for cust_id, cust in sorted(customers.items(), key=lambda x: x[1]['total_mrr'], reverse=True):
            # Main customer row
            customer_row = {
                'id': f"cust_{cust_id}",
                'expandable': True,
                'customer_name': f"▶ {cust['customer_name']}",
                'customer_id': cust_id,
                'subscriptions': len(cust['subscriptions']),
                'total_mrr': f"{cust['total_mrr']:,.0f} kr"
            }

            # Sub rows for subscriptions
            customer_row['sub_rows'] = []
            for sub in cust['subscriptions']:
                # Format sub-row with vessel and call sign
                sub_name = f"  → {sub['product_name']}"
                if sub.get('vessel_name') and sub['vessel_name'] != 'N/A':
                    sub_name += f" | {sub['vessel_name']}"
                if sub.get('call_sign') and sub['call_sign'] != 'N/A':
                    sub_name += f" ({sub['call_sign']})"

                customer_row['sub_rows'].append({
                    'customer_name': sub_name,
                    'customer_id': sub['subscription_id'],
                    'subscriptions': sub['status'],
                    'total_mrr': sub['mrr']
                })

            data.append(customer_row)

        stats = [
            {'label': 'Totalt kunder', 'value': len(customers), 'class': ''},
            {'label': 'Totalt subscriptions', 'value': len(subscriptions), 'class': ''},
            {'label': 'Total MRR', 'value': f"{sum(c['total_mrr'] for c in customers.values()):,.0f} kr", 'class': ''}
        ]

        columns = [
            {'key': 'customer_name', 'label': 'Kunde', 'class': ''},
            {'key': 'customer_id', 'label': 'Kunde ID', 'class': ''},
            {'key': 'subscriptions', 'label': 'Subscriptions', 'class': 'number'},
            {'key': 'total_mrr', 'label': 'MRR', 'class': 'number'}
        ]

        return templates.TemplateResponse("drilldown.html", {
            "request": request,
            "title": "Selskaper",
            "subtitle": "Alle aktive selskaper med deres subscriptions",
            "stats": stats,
            "columns": columns,
            "data": data
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drilldown failed: {str(e)}")


@app.get("/api/drilldown/subscriptions", response_class=HTMLResponse)
async def drilldown_subscriptions(
    request: Request,
    session: AsyncSession = Depends(get_session),
    status_filter: str = "all"
):
    """Drilldown: All active subscriptions with optional status filter"""
    try:
        from sqlalchemy import select

        # Build query based on filter
        if status_filter == "live":
            stmt = select(Subscription).where(
                Subscription.status == "live"
            ).order_by(Subscription.customer_name)
        elif status_filter == "non_renewing":
            stmt = select(Subscription).where(
                Subscription.status == "non_renewing"
            ).order_by(Subscription.customer_name)
        else:  # all
            stmt = select(Subscription).where(
                Subscription.status.in_(["live", "non_renewing"])
            ).order_by(Subscription.customer_name)

        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        calculator = MetricsCalculator(session)
        total_mrr = 0

        data = []
        for sub in subscriptions:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            total_mrr += mrr

            data.append({
                'subscription_id': sub.id,
                'customer_name': sub.customer_name,
                'product_name': sub.plan_name or 'N/A',
                'amount': f"{sub.amount:,.0f} kr",
                'interval': f"{sub.interval_unit} {sub.interval}",
                'status': sub.status,
                'mrr': f"{mrr:,.0f} kr",
                'activated_at': sub.activated_at.strftime('%d.%m.%Y') if sub.activated_at else 'N/A'
            })

        stats = [
            {'label': 'Totalt subscriptions', 'value': len(subscriptions), 'class': ''},
            {'label': 'Live', 'value': len([s for s in subscriptions if s.status == 'live']), 'class': ''},
            {'label': 'Non-renewing', 'value': len([s for s in subscriptions if s.status == 'non_renewing']), 'class': ''},
            {'label': 'Total MRR', 'value': f"{total_mrr:,.0f} kr", 'class': ''}
        ]

        columns = [
            {'key': 'subscription_id', 'label': 'Subscription ID', 'class': ''},
            {'key': 'customer_name', 'label': 'Kunde', 'class': ''},
            {'key': 'product_name', 'label': 'Produkt', 'class': ''},
            {'key': 'amount', 'label': 'Beløp', 'class': 'number'},
            {'key': 'interval', 'label': 'Intervall', 'class': ''},
            {'key': 'status', 'label': 'Status', 'class': ''},
            {'key': 'mrr', 'label': 'MRR', 'class': 'number'},
            {'key': 'activated_at', 'label': 'Aktivert', 'class': ''}
        ]

        return templates.TemplateResponse("drilldown.html", {
            "request": request,
            "title": "Subscriptions",
            "subtitle": "Alle aktive subscriptions",
            "stats": stats,
            "columns": columns,
            "data": data,
            "current_filter": status_filter,
            "filters": [
                {"value": "all", "label": "Alle"},
                {"value": "live", "label": "Live"},
                {"value": "non_renewing", "label": "Non-renewing"}
            ]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drilldown failed: {str(e)}")


@app.get("/api/drilldown/mrr", response_class=HTMLResponse)
async def drilldown_mrr(request: Request, session: AsyncSession = Depends(get_session)):
    """Drilldown: MRR breakdown by subscription"""
    try:
        from sqlalchemy import select

        stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"])
        ).order_by(Subscription.customer_name)

        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        calculator = MetricsCalculator(session)
        total_mrr = 0

        # Group by plan
        plan_mrr = {}

        data = []
        for sub in subscriptions:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            total_mrr += mrr

            # Add to plan aggregation
            plan_key = sub.plan_name or 'Unknown'
            if plan_key not in plan_mrr:
                plan_mrr[plan_key] = {'mrr': 0, 'count': 0}
            plan_mrr[plan_key]['mrr'] += mrr
            plan_mrr[plan_key]['count'] += 1

            data.append({
                'customer_name': sub.customer_name,
                'plan_name': sub.plan_name or 'N/A',
                'status': sub.status,
                'mrr': f"{mrr:,.0f} kr",
                'activated_at': sub.activated_at.strftime('%d.%m.%Y') if sub.activated_at else 'N/A'
            })

        # Prepare plan summary for stats
        top_plans = sorted(plan_mrr.items(), key=lambda x: x[1]['mrr'], reverse=True)[:3]

        stats = [
            {'label': 'Total MRR', 'value': f"{total_mrr:,.0f} kr", 'class': ''},
            {'label': 'ARR', 'value': f"{total_mrr * 12:,.0f} kr", 'class': ''},
            {'label': 'Subscriptions', 'value': len(subscriptions), 'class': ''},
            {'label': f'Største plan: {top_plans[0][0] if top_plans else "N/A"}',
             'value': f"{top_plans[0][1]['mrr']:,.0f} kr" if top_plans else '0 kr', 'class': ''}
        ]

        columns = [
            {'key': 'customer_name', 'label': 'Kunde', 'class': ''},
            {'key': 'plan_name', 'label': 'Plan', 'class': ''},
            {'key': 'status', 'label': 'Status', 'class': ''},
            {'key': 'mrr', 'label': 'MRR', 'class': 'number'},
            {'key': 'activated_at', 'label': 'Aktivert', 'class': ''}
        ]

        return templates.TemplateResponse("drilldown.html", {
            "request": request,
            "title": "MRR Breakdown",
            "subtitle": "Monthly Recurring Revenue per subscription",
            "stats": stats,
            "columns": columns,
            "data": data
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drilldown failed: {str(e)}")


@app.get("/api/drilldown/arpu", response_class=HTMLResponse)
async def drilldown_arpu(request: Request, session: AsyncSession = Depends(get_session)):
    """Drilldown: ARPU by customer"""
    try:
        from sqlalchemy import select, func

        # Get all active subscriptions grouped by customer
        stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"])
        ).order_by(Subscription.customer_name)

        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        calculator = MetricsCalculator(session)

        # Group by customer
        customer_mrr = {}
        for sub in subscriptions:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            customer_name = sub.customer_name

            if customer_name not in customer_mrr:
                customer_mrr[customer_name] = {
                    'mrr': 0,
                    'subscriptions': 0,
                    'plans': []
                }
            customer_mrr[customer_name]['mrr'] += mrr
            customer_mrr[customer_name]['subscriptions'] += 1
            customer_mrr[customer_name]['plans'].append(sub.plan_name or 'N/A')

        # Calculate stats
        total_customers = len(customer_mrr)
        total_mrr = sum(c['mrr'] for c in customer_mrr.values())
        arpu = total_mrr / total_customers if total_customers > 0 else 0

        # Prepare data sorted by MRR
        data = []
        for customer, info in sorted(customer_mrr.items(), key=lambda x: x[1]['mrr'], reverse=True):
            data.append({
                'customer_name': customer,
                'subscriptions': info['subscriptions'],
                'plans': ', '.join(set(info['plans']))[:50] + '...' if len(set(info['plans'])) > 2 else ', '.join(set(info['plans'])),
                'mrr': f"{info['mrr']:,.0f} kr"
            })

        stats = [
            {'label': 'ARPU', 'value': f"{arpu:,.0f} kr", 'class': ''},
            {'label': 'Total kunder', 'value': total_customers, 'class': ''},
            {'label': 'Total MRR', 'value': f"{total_mrr:,.0f} kr", 'class': ''},
            {'label': 'Median MRR', 'value': f"{sorted([c['mrr'] for c in customer_mrr.values()])[len(customer_mrr)//2] if customer_mrr else 0:,.0f} kr", 'class': ''}
        ]

        columns = [
            {'key': 'customer_name', 'label': 'Kunde', 'class': ''},
            {'key': 'subscriptions', 'label': 'Antall abonnement', 'class': 'number'},
            {'key': 'plans', 'label': 'Planer', 'class': ''},
            {'key': 'mrr', 'label': 'MRR', 'class': 'number'}
        ]

        return templates.TemplateResponse("drilldown.html", {
            "request": request,
            "title": "ARPU (Average Revenue Per User)",
            "subtitle": "Revenue breakdown per customer",
            "stats": stats,
            "columns": columns,
            "data": data
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drilldown failed: {str(e)}")


@app.get("/api/drilldown/churn", response_class=HTMLResponse)
async def drilldown_churn(request: Request, session: AsyncSession = Depends(get_session)):
    """Drilldown: Churned customers grouped by month with drilldown"""
    try:
        from sqlalchemy import select, func
        from datetime import datetime
        from models.subscription import ChurnedCustomer
        from collections import defaultdict

        # Get all churned customers (last 12 months) - eldste først, nyeste nederst
        stmt = select(ChurnedCustomer).order_by(ChurnedCustomer.cancelled_date.asc())
        result = await session.execute(stmt)
        all_churned = result.scalars().all()

        # Group by month
        monthly_churn = defaultdict(list)
        for customer in all_churned:
            if customer.cancelled_date:
                month_key = customer.cancelled_date.strftime('%Y-%m')
                monthly_churn[month_key].append(customer)

        # Calculate totals
        total_churned_customers = len(all_churned)
        total_churned_mrr = sum(c.amount for c in all_churned)

        # Build data with expandable rows (eldste måneder først, nyeste nederst)
        data = []
        for month_key in sorted(monthly_churn.keys(), reverse=False):
            customers = monthly_churn[month_key]
            month_mrr = sum(c.amount for c in customers)

            # Parse month for display
            from datetime import datetime
            month_date = datetime.strptime(month_key, '%Y-%m')
            month_display = month_date.strftime('%B %Y')

            # Main month row
            month_row = {
                'id': f"month_{month_key}",
                'expandable': True,
                'month': f"▶ {month_display}",
                'customers': len(customers),
                'churned_mrr': f"-{month_mrr:,.0f} kr",
                'avg_mrr': f"-{month_mrr / len(customers):,.0f} kr",
                'details': ''
            }

            # Sub rows for individual customers
            month_row['sub_rows'] = []
            for customer in sorted(customers, key=lambda x: x.amount, reverse=True):
                month_row['sub_rows'].append({
                    'month': f"  → {customer.customer_name}",
                    'customers': customer.plan_name or 'N/A',
                    'churned_mrr': f"-{customer.amount:,.0f} kr",
                    'avg_mrr': customer.cancelled_date.strftime('%d.%m.%Y') if customer.cancelled_date else 'N/A',
                    'details': customer.cancellation_reason or 'Ikke oppgitt'
                })

            data.append(month_row)

        stats = [
            {'label': 'Totalt churned kunder', 'value': total_churned_customers, 'class': 'negative'},
            {'label': 'Total churned MRR', 'value': f"-{total_churned_mrr:,.0f} kr", 'class': 'negative'},
            {'label': 'Avg. churned MRR', 'value': f"-{total_churned_mrr / total_churned_customers if total_churned_customers else 0:,.0f} kr", 'class': 'negative'},
            {'label': 'Måneder', 'value': len(monthly_churn), 'class': ''}
        ]

        columns = [
            {'key': 'month', 'label': 'Måned / Kunde', 'class': ''},
            {'key': 'customers', 'label': 'Antall / Plan', 'class': ''},
            {'key': 'churned_mrr', 'label': 'Churned MRR', 'class': 'number negative'},
            {'key': 'avg_mrr', 'label': 'Snitt / Dato', 'class': 'number negative'},
            {'key': 'details', 'label': 'Detaljer / Årsak', 'class': ''}
        ]

        return templates.TemplateResponse("drilldown.html", {
            "request": request,
            "title": "Churn Analysis",
            "subtitle": "Månedlig churn-oversikt med drilldown på kundenivå",
            "stats": stats,
            "columns": columns,
            "data": data
        })
    except Exception as e:
        import traceback
        print(f"Error in drilldown_churn: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Drilldown failed: {str(e)}")


@app.get("/api/drilldown/new-mrr", response_class=HTMLResponse)
async def drilldown_new_mrr(request: Request, session: AsyncSession = Depends(get_session)):
    """Drilldown: New MRR from last 30 days"""
    try:
        from sqlalchemy import select
        from datetime import datetime, timedelta

        # Get subscriptions activated in last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)

        stmt = select(Subscription).where(
            Subscription.activated_at >= thirty_days_ago,
            Subscription.status.in_(["live", "non_renewing"])
        ).order_by(Subscription.activated_at.desc())

        result = await session.execute(stmt)
        new_subscriptions = result.scalars().all()

        calculator = MetricsCalculator(session)
        total_new_mrr = 0

        data = []
        for sub in new_subscriptions:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            total_new_mrr += mrr

            data.append({
                'activated_at': sub.activated_at.strftime('%d.%m.%Y') if sub.activated_at else 'N/A',
                'customer_name': sub.customer_name,
                'plan_name': sub.plan_name or 'N/A',
                'mrr': f"{mrr:,.0f} kr",
                'status': sub.status
            })

        stats = [
            {'label': 'Nye subscriptions', 'value': len(new_subscriptions), 'class': ''},
            {'label': 'New MRR', 'value': f"{total_new_mrr:,.0f} kr", 'class': ''},
            {'label': 'Avg. MRR per kunde', 'value': f"{total_new_mrr / len(new_subscriptions) if new_subscriptions else 0:,.0f} kr", 'class': ''},
            {'label': 'Periode', 'value': 'Siste 30 dager', 'class': ''}
        ]

        columns = [
            {'key': 'activated_at', 'label': 'Aktivert', 'class': ''},
            {'key': 'customer_name', 'label': 'Kunde', 'class': ''},
            {'key': 'plan_name', 'label': 'Plan', 'class': ''},
            {'key': 'mrr', 'label': 'MRR', 'class': 'number'},
            {'key': 'status', 'label': 'Status', 'class': ''}
        ]

        return templates.TemplateResponse("drilldown.html", {
            "request": request,
            "title": "New MRR",
            "subtitle": "New subscriptions last 30 days",
            "stats": stats,
            "columns": columns,
            "data": data
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drilldown failed: {str(e)}")


@app.get("/api/customers/all", response_class=HTMLResponse)
async def all_customers(request: Request, session: AsyncSession = Depends(get_session)):
    """Complete customer overview with active and churned customers"""
    try:
        from sqlalchemy import select
        from models.subscription import ChurnedCustomer
        from datetime import datetime
        import io

        # Get all active subscriptions
        active_stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"])
        ).order_by(Subscription.customer_name)

        active_result = await session.execute(active_stmt)
        active_subscriptions = active_result.scalars().all()

        # Group active customers
        active_customers = {}
        calculator = MetricsCalculator(session)

        for sub in active_subscriptions:
            if sub.customer_id not in active_customers:
                active_customers[sub.customer_id] = {
                    'customer_id': sub.customer_id,
                    'customer_name': sub.customer_name,
                    'status': 'Aktiv',
                    'subscriptions': [],
                    'total_mrr': 0,
                    'activated_at': None,
                    'cancelled_at': None,
                    'churn_reason': None
                }

            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            active_customers[sub.customer_id]['subscriptions'].append({
                'plan_name': sub.plan_name or 'N/A',
                'mrr': mrr,
                'vessel_name': sub.vessel_name or '',
                'call_sign': sub.call_sign or ''
            })
            active_customers[sub.customer_id]['total_mrr'] += mrr

            # Track earliest activation date
            if sub.activated_at:
                if not active_customers[sub.customer_id]['activated_at'] or sub.activated_at < active_customers[sub.customer_id]['activated_at']:
                    active_customers[sub.customer_id]['activated_at'] = sub.activated_at

        # Get all churned customers
        churned_stmt = select(ChurnedCustomer).order_by(ChurnedCustomer.cancelled_date.desc())
        churned_result = await session.execute(churned_stmt)
        churned_customers_list = churned_result.scalars().all()

        # Build complete customer list
        all_customers_list = []

        # Add churned customers FIRST (nyeste først - already sorted desc by cancelled_date)
        for churned in churned_customers_list:
            all_customers_list.append({
                'customer_id': churned.customer_id,
                'customer_name': churned.customer_name,
                'status': 'Churned',
                'plans': churned.plan_name or 'N/A',
                'vessels': 'N/A',
                'call_signs': 'N/A',
                'mrr': f"-{churned.amount:,.0f} kr",
                'mrr_raw': -churned.amount,
                'activated_at': 'N/A',
                'cancelled_at': churned.cancelled_date.strftime('%d.%m.%Y') if churned.cancelled_date else 'N/A',
                'churn_reason': churned.cancellation_reason or 'Ikke oppgitt',
                'status_class': 'negative',
                'sort_date': churned.cancelled_date if churned.cancelled_date else datetime.min
            })

        # Add active customers (sorted by activation date, newest first)
        active_list = []
        for cust_id, cust in active_customers.items():
            plans = ', '.join([s['plan_name'] for s in cust['subscriptions']])
            vessels = ', '.join([s['vessel_name'] for s in cust['subscriptions'] if s['vessel_name']])
            call_signs = ', '.join([s['call_sign'] for s in cust['subscriptions'] if s['call_sign']])

            active_list.append({
                'customer_id': cust['customer_id'],
                'customer_name': cust['customer_name'],
                'status': 'Aktiv',
                'plans': plans,
                'vessels': vessels if vessels else 'N/A',
                'call_signs': call_signs if call_signs else 'N/A',
                'mrr': f"{cust['total_mrr']:,.0f} kr",
                'mrr_raw': cust['total_mrr'],
                'activated_at': cust['activated_at'].strftime('%d.%m.%Y') if cust['activated_at'] else 'N/A',
                'cancelled_at': '',
                'churn_reason': '',
                'status_class': 'positive',
                'sort_date': cust['activated_at'] if cust['activated_at'] else datetime.min
            })

        # Sort active customers by activation date (newest first)
        active_list.sort(key=lambda x: x['sort_date'], reverse=True)
        all_customers_list.extend(active_list)

        # Calculate stats
        total_active_mrr = sum(c['total_mrr'] for c in active_customers.values())
        total_churned_mrr = sum(c.amount for c in churned_customers_list)

        stats = [
            {'label': 'Aktive kunder', 'value': len(active_customers), 'class': 'positive'},
            {'label': 'Aktiv MRR', 'value': f"{total_active_mrr:,.0f} kr", 'class': 'positive'},
            {'label': 'Churned kunder', 'value': len(churned_customers_list), 'class': 'negative'},
            {'label': 'Churned MRR', 'value': f"-{total_churned_mrr:,.0f} kr", 'class': 'negative'},
            {'label': 'Totalt kunder', 'value': len(all_customers_list), 'class': ''}
        ]

        columns = [
            {'key': 'customer_name', 'label': 'Kunde', 'class': ''},
            {'key': 'customer_id', 'label': 'Kunde ID', 'class': ''},
            {'key': 'status', 'label': 'Status', 'class': ''},
            {'key': 'plans', 'label': 'Planer', 'class': ''},
            {'key': 'vessels', 'label': 'Fartøy', 'class': ''},
            {'key': 'call_signs', 'label': 'Kallesignal', 'class': ''},
            {'key': 'mrr', 'label': 'MRR', 'class': 'number'},
            {'key': 'activated_at', 'label': 'Aktivert', 'class': ''},
            {'key': 'cancelled_at', 'label': 'Kansellert', 'class': ''},
            {'key': 'churn_reason', 'label': 'Årsak', 'class': ''}
        ]

        return templates.TemplateResponse("customers_all.html", {
            "request": request,
            "title": "Abonnenter og oppsigelser",
            "subtitle": "Komplett oversikt over aktive og churned abonnenter",
            "stats": stats,
            "columns": columns,
            "data": all_customers_list
        })
    except Exception as e:
        import traceback
        print(f"Error in all_customers: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch customers: {str(e)}")


@app.get("/api/customers/export")
async def export_customers_csv(session: AsyncSession = Depends(get_session)):
    """Export all customers to CSV"""
    try:
        from sqlalchemy import select
        from models.subscription import ChurnedCustomer
        from datetime import datetime
        import io
        import csv

        # Get all active subscriptions
        active_stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"])
        ).order_by(Subscription.customer_name)

        active_result = await session.execute(active_stmt)
        active_subscriptions = active_result.scalars().all()

        # Group active customers
        active_customers = {}
        calculator = MetricsCalculator(session)

        for sub in active_subscriptions:
            if sub.customer_id not in active_customers:
                active_customers[sub.customer_id] = {
                    'customer_id': sub.customer_id,
                    'customer_name': sub.customer_name,
                    'status': 'Aktiv',
                    'subscriptions': [],
                    'total_mrr': 0,
                    'activated_at': None,
                    'cancelled_at': '',
                    'churn_reason': ''
                }

            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            active_customers[sub.customer_id]['subscriptions'].append({
                'plan_name': sub.plan_name or 'N/A',
                'mrr': mrr,
                'vessel_name': sub.vessel_name or '',
                'call_sign': sub.call_sign or ''
            })
            active_customers[sub.customer_id]['total_mrr'] += mrr

            # Track earliest activation date
            if sub.activated_at:
                if not active_customers[sub.customer_id]['activated_at'] or sub.activated_at < active_customers[sub.customer_id]['activated_at']:
                    active_customers[sub.customer_id]['activated_at'] = sub.activated_at

        # Get all churned customers
        churned_stmt = select(ChurnedCustomer).order_by(ChurnedCustomer.cancelled_date.desc())
        churned_result = await session.execute(churned_stmt)
        churned_customers_list = churned_result.scalars().all()

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        # Write header
        writer.writerow([
            'Kunde ID', 'Kundenavn', 'Status', 'Planer', 'Fartøy',
            'MRR (kr)', 'Aktivert', 'Kansellert', 'Churn Årsak'
        ])

        # Write churned customers FIRST (nyeste først - already sorted desc by cancelled_date)
        for churned in churned_customers_list:
            writer.writerow([
                churned.customer_id,
                churned.customer_name,
                'Churned',
                churned.plan_name or 'N/A',
                'N/A',
                f"-{churned.amount:.0f}",
                'N/A',
                churned.cancelled_date.strftime('%d.%m.%Y') if churned.cancelled_date else 'N/A',
                churned.cancellation_reason or 'Ikke oppgitt'
            ])

        # Write active customers (sorted by activation date, newest first)
        active_list = []
        for cust_id, cust in active_customers.items():
            active_list.append({
                'customer_id': cust['customer_id'],
                'customer_name': cust['customer_name'],
                'subscriptions': cust['subscriptions'],
                'total_mrr': cust['total_mrr'],
                'activated_at': cust['activated_at']
            })

        # Sort by activation date (newest first)
        active_list.sort(key=lambda x: x['activated_at'] if x['activated_at'] else datetime.min, reverse=True)

        for cust in active_list:
            plans = ', '.join([s['plan_name'] for s in cust['subscriptions']])
            vessels = ', '.join([s['vessel_name'] for s in cust['subscriptions'] if s['vessel_name']])

            writer.writerow([
                cust['customer_id'],
                cust['customer_name'],
                'Aktiv',
                plans,
                vessels if vessels else 'N/A',
                f"{cust['total_mrr']:.0f}",
                cust['activated_at'].strftime('%d.%m.%Y') if cust['activated_at'] else 'N/A',
                '',
                ''
            ])

        # Prepare response
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=kundeliste_{datetime.now().strftime('%Y%m%d')}.csv"
            }
        )

    except Exception as e:
        import traceback
        print(f"Error in export_customers_csv: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/api/forecast", response_class=HTMLResponse)
async def mrr_forecast(request: Request, session: AsyncSession = Depends(get_session)):
    """MRR Forecast based on non-renewing subscriptions"""
    try:
        from sqlalchemy import select
        from datetime import datetime, timedelta
        import json

        # Calculate current MRR from all active subscriptions
        active_stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"])
        )
        active_result = await session.execute(active_stmt)
        active_subscriptions = active_result.scalars().all()

        calculator = MetricsCalculator(session)
        current_mrr = 0
        for sub in active_subscriptions:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            current_mrr += mrr

        # Get all non-renewing subscriptions
        non_renewing_stmt = select(Subscription).where(
            Subscription.status == "non_renewing"
        ).order_by(Subscription.customer_name)

        non_renewing_result = await session.execute(non_renewing_stmt)
        non_renewing_subs = non_renewing_result.scalars().all()

        # Calculate non-renewing MRR and separate those with/without expiration dates
        # For non_renewing subscriptions, use cancelled_at as the expiry date (when they were set to non-renewing)
        non_renewing_mrr = 0
        subs_with_dates = []
        subs_without_dates = []

        for sub in non_renewing_subs:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            non_renewing_mrr += mrr

            # Use expires_at if available, otherwise use cancelled_at
            expiry_date = sub.expires_at or sub.cancelled_at
            if expiry_date:
                sub._expiry_date = expiry_date  # Store for later use
                subs_with_dates.append(sub)
            else:
                subs_without_dates.append(sub)

        # Generate forecast data for next 12 months
        forecast_months = 12
        today = datetime.now()

        # Create monthly buckets
        forecast_data = {
            'labels': [],
            'mrr': [],
            'baseline': []
        }

        # Track MRR changes per month (only for subscriptions with expiration dates)
        monthly_losses = {}
        for sub in subs_with_dates:
            # Calculate which month this subscription expires
            month_key = sub._expiry_date.strftime('%Y-%m')
            mrr_loss = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)

            if month_key not in monthly_losses:
                monthly_losses[month_key] = 0
            monthly_losses[month_key] += mrr_loss

        # Generate forecast
        forecasted_mrr = current_mrr
        for i in range(forecast_months + 1):
            month_date = today + timedelta(days=30 * i)
            month_key = month_date.strftime('%Y-%m')
            month_label = month_date.strftime('%b %Y')

            forecast_data['labels'].append(month_label)
            forecast_data['baseline'].append(current_mrr)

            # Apply losses for this month
            if month_key in monthly_losses:
                forecasted_mrr -= monthly_losses[month_key]

            forecast_data['mrr'].append(forecasted_mrr)

        # Calculate final forecasted MRR and impact
        final_forecasted_mrr = forecasted_mrr
        forecasted_impact = final_forecasted_mrr - current_mrr

        # Get upcoming cancellations for table (with expiration dates)
        upcoming_cancellations = []
        for sub in subs_with_dates:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            days_left = (sub._expiry_date - today).days

            upcoming_cancellations.append({
                'customer_name': sub.customer_name or 'N/A',
                'product_name': sub.plan_name or 'N/A',
                'vessel_name': sub.vessel_name or 'N/A',
                'mrr': f"{mrr:,.0f} kr",
                'expires_at': sub._expiry_date.strftime('%d.%m.%Y'),
                'days_left': days_left if days_left >= 0 else 0
            })

        # Also list subscriptions without expiration dates
        no_expiry_list = []
        for sub in subs_without_dates:
            mrr = calculator._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
            no_expiry_list.append({
                'customer_name': sub.customer_name or 'N/A',
                'product_name': sub.plan_name or 'N/A',
                'vessel_name': sub.vessel_name or 'N/A',
                'mrr': f"{mrr:,.0f} kr"
            })

        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "current_mrr": f"{current_mrr:,.0f} kr",
            "non_renewing_mrr": f"{non_renewing_mrr:,.0f} kr",
            "non_renewing_count": len(non_renewing_subs),
            "forecasted_mrr": f"{final_forecasted_mrr:,.0f} kr",
            "impact": f"{abs(forecasted_impact):,.0f} kr",
            "forecasted_impact": forecasted_impact,
            "forecast_months": forecast_months,
            "forecast_data": json.dumps(forecast_data),
            "upcoming_cancellations": upcoming_cancellations,
            "no_expiry_list": no_expiry_list,
            "subs_with_dates_count": len(subs_with_dates),
            "subs_without_dates_count": len(subs_without_dates)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")


# ============================================================================
# INVOICE-BASED MRR ENDPOINTS
# Separate system for calculating MRR from invoices (not subscriptions)
# ============================================================================

@app.post("/api/invoices/sync")
async def sync_invoices(
    zoho: ZohoClient = Depends(get_zoho_client),
    session: AsyncSession = Depends(get_session),
):
    """
    Sync invoices from Zoho Billing and calculate MRR based on invoice line items

    This uses invoice periods (from description field) to calculate accurate MRR
    """
    try:
        import httpx
        from models.invoice import Invoice, InvoiceLineItem
        from services.invoice import InvoiceService

        invoice_service = InvoiceService(session)
        headers = await zoho._get_headers()

        # Fetch invoices from Zoho
        print("Fetching invoices from Zoho...")
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Get all invoices (paginated)
            all_invoices = []
            page = 1
            per_page = 200

            while True:
                response = await client.get(
                    f"{zoho.base_url}/billing/v1/invoices",
                    headers=headers,
                    params={"per_page": per_page, "page": page}
                )
                response.raise_for_status()
                data = response.json()

                invoices = data.get("invoices", [])
                if not invoices:
                    break

                all_invoices.extend(invoices)

                if len(invoices) < per_page:
                    break

                page += 1

            print(f"Fetched {len(all_invoices)} invoices from Zoho")

            # Process each invoice and get full details
            synced_count = 0
            total_invoices = len(all_invoices)

            for inv_data in all_invoices:
                invoice_id = inv_data["invoice_id"]

                # Get full invoice details including line items
                detail_response = await client.get(
                    f"{zoho.base_url}/billing/v1/invoices/{invoice_id}",
                    headers=headers
                )
                detail_response.raise_for_status()
                invoice_detail = detail_response.json().get("invoice", {})

                # Rate limiting: sleep 0.3s between requests to avoid 429 errors
                import asyncio
                await asyncio.sleep(0.3)

                # Parse dates
                def parse_date(date_str):
                    if not date_str:
                        return None
                    try:
                        if isinstance(date_str, datetime):
                            return date_str.replace(tzinfo=None)
                        date_str = str(date_str).strip()
                        if "T" in date_str:
                            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            return dt.replace(tzinfo=None)
                        else:
                            from dateutil import parser
                            dt = parser.parse(date_str)
                            return dt.replace(tzinfo=None)
                    except Exception as e:
                        print(f"Warning: Failed to parse date '{date_str}': {e}")
                        return None

                invoice_date = parse_date(invoice_detail.get("invoice_date"))
                due_date = parse_date(invoice_detail.get("due_date"))
                created_time = parse_date(invoice_detail.get("created_time"))
                updated_time = parse_date(invoice_detail.get("updated_time"))

                # Create or update invoice
                invoice = await session.get(Invoice, invoice_id)

                if invoice:
                    # Update existing
                    invoice.invoice_number = invoice_detail.get("invoice_number", "")
                    invoice.invoice_date = invoice_date
                    invoice.due_date = due_date
                    invoice.customer_id = invoice_detail.get("customer_id", "")
                    invoice.customer_name = invoice_detail.get("customer_name", "")
                    invoice.customer_email = invoice_detail.get("email", "")
                    invoice.currency_code = invoice_detail.get("currency_code", "NOK")
                    invoice.sub_total = float(invoice_detail.get("sub_total", 0))
                    invoice.tax_total = float(invoice_detail.get("tax_total", 0))
                    invoice.total = float(invoice_detail.get("total", 0))
                    invoice.balance = float(invoice_detail.get("balance", 0))
                    invoice.status = invoice_detail.get("status", "")
                    invoice.transaction_type = invoice_detail.get("transaction_type", "")
                    invoice.created_time = created_time
                    invoice.updated_time = updated_time
                    invoice.last_synced = datetime.utcnow()
                else:
                    # Create new
                    invoice = Invoice(
                        id=invoice_id,
                        invoice_number=invoice_detail.get("invoice_number", ""),
                        invoice_date=invoice_date,
                        due_date=due_date,
                        customer_id=invoice_detail.get("customer_id", ""),
                        customer_name=invoice_detail.get("customer_name", ""),
                        customer_email=invoice_detail.get("email", ""),
                        currency_code=invoice_detail.get("currency_code", "NOK"),
                        sub_total=float(invoice_detail.get("sub_total", 0)),
                        tax_total=float(invoice_detail.get("tax_total", 0)),
                        total=float(invoice_detail.get("total", 0)),
                        balance=float(invoice_detail.get("balance", 0)),
                        status=invoice_detail.get("status", ""),
                        transaction_type=invoice_detail.get("transaction_type", ""),
                        created_time=created_time,
                        updated_time=updated_time,
                    )
                    session.add(invoice)

                # Process line items
                line_items = invoice_detail.get("invoice_items", [])

                # Delete existing line items for this invoice
                from sqlalchemy import delete
                stmt_delete = delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)
                await session.execute(stmt_delete)

                # Create new line items
                for item_data in line_items:
                    # Calculate MRR from line item
                    mrr_calc = invoice_service.calculate_mrr_from_line_item(item_data)

                    line_item = InvoiceLineItem(
                        invoice_id=invoice_id,
                        item_id=item_data.get("item_id", ""),
                        product_id=item_data.get("product_id", ""),
                        subscription_id=item_data.get("subscription_id", ""),
                        name=item_data.get("name", ""),
                        description=item_data.get("description", ""),
                        code=item_data.get("code", ""),
                        unit=item_data.get("unit", ""),
                        price=float(item_data.get("price", 0)),
                        quantity=int(item_data.get("quantity", 1)),
                        item_total=float(item_data.get("item_total", 0)),
                        tax_percentage=float(item_data.get("tax_percentage", 0)),
                        tax_name=item_data.get("tax_name", ""),
                        period_start_date=mrr_calc["period_start_date"],
                        period_end_date=mrr_calc["period_end_date"],
                        period_months=mrr_calc["period_months"],
                        mrr_per_month=mrr_calc["mrr_per_month"],
                    )
                    session.add(line_item)

                synced_count += 1

                # Commit and log progress periodically
                if synced_count % 50 == 0:
                    await session.commit()
                    progress_pct = (synced_count / total_invoices) * 100
                    print(f"Progress: {synced_count}/{total_invoices} invoices ({progress_pct:.1f}%)")

            await session.commit()
            print(f"✓ Synced {synced_count} invoices with line items")

        # Generate monthly snapshots for last 12 months
        print("\nGenerating monthly MRR snapshots...")
        today = datetime.utcnow()
        snapshots_created = []

        for i in range(12):
            month_date = today - relativedelta(months=i)
            month_str = month_date.strftime("%Y-%m")

            try:
                await invoice_service.generate_monthly_snapshot(month_str)
                snapshots_created.append(month_str)
                print(f"  ✓ Created snapshot for {month_str}")
            except Exception as e:
                print(f"  ✗ Failed to create snapshot for {month_str}: {e}")

        print(f"✓ Generated {len(snapshots_created)} monthly snapshots")

        return {
            "status": "success",
            "synced_invoices": synced_count,
            "snapshots_created": len(snapshots_created),
            "message": f"Successfully synced {synced_count} invoices and generated {len(snapshots_created)} monthly snapshots",
        }

    except Exception as e:
        await session.rollback()
        import traceback
        error_detail = f"Invoice sync failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Invoice sync failed: {str(e)}")


@app.get("/api/invoices/dashboard", response_class=HTMLResponse)
async def invoices_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Invoice-based MRR dashboard (separate from subscription-based MRR)
    """
    try:
        from services.invoice import InvoiceService

        invoice_service = InvoiceService(session)

        # Get current month snapshot
        current_month = datetime.utcnow().strftime("%Y-%m")

        # Calculate current metrics
        mrr = await invoice_service.get_mrr_for_month(current_month)
        arr = mrr * 12
        total_customers = await invoice_service.get_unique_customers_for_month(current_month)
        arpu = mrr / total_customers if total_customers > 0 else 0

        metrics = {
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "total_customers": total_customers,
            "arpu": round(arpu, 2),
            "snapshot_date": datetime.utcnow(),
        }

        return templates.TemplateResponse(
            "invoices_dashboard.html",
            {
                "request": request,
                "metrics": metrics,
                "active_page": "invoices",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invoice dashboard failed: {str(e)}")


@app.get("/api/invoices/trends", response_class=HTMLResponse)
async def invoices_trends(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Monthly trends view for invoice-based MRR
    """
    try:
        from services.invoice import InvoiceService

        invoice_service = InvoiceService(session)
        trends = await invoice_service.get_monthly_trends(months=12)

        return templates.TemplateResponse(
            "invoices_trends.html",
            {
                "request": request,
                "trends": trends,
                "active_page": "invoices",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invoice trends failed: {str(e)}")


@app.get("/api/invoices/monthly-trends")
async def get_invoice_monthly_trends(
    session: AsyncSession = Depends(get_session),
    months: int = 12,
):
    """
    Get month-over-month trends for invoice-based MRR (JSON API)
    """
    try:
        from services.invoice import InvoiceService

        invoice_service = InvoiceService(session)
        trends = await invoice_service.get_monthly_trends(months=months)

        return {
            "status": "success",
            "trends": trends,
            "data_source": "invoice_calculation",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get invoice trends: {str(e)}")


# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@app.get("/api/dump-non-renewing")
async def dump_non_renewing():
    """Dump raw data for all non-renewing subscriptions from Zoho API"""
    try:
        zoho = ZohoClient(settings.zoho_org_id, settings.zoho_client_id, settings.zoho_client_secret, settings.zoho_refresh_token)
        await zoho.initialize()

        all_subs = await zoho.list_subscriptions()
        non_renewing = [sub for sub in all_subs if sub.get("status") == "non_renewing"]

        return {
            "total_non_renewing": len(non_renewing),
            "subscriptions": non_renewing[:5]  # Return first 5 for readability
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dump failed: {str(e)}")


@app.get("/api/debug-invoices")
async def debug_invoices(zoho: ZohoClient = Depends(get_zoho_client)):
    """Debug endpoint to analyze invoice, product, and plan structure from Zoho"""
    try:
        import json
        import httpx

        headers = await zoho._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch invoices list
            invoices_response = await client.get(
                f"{zoho.base_url}/billing/v1/invoices",
                headers=headers,
                params={"per_page": 5}
            )
            invoices_response.raise_for_status()
            invoices_data = invoices_response.json()

            # Get first 3 invoice IDs and fetch full details including line items
            invoice_details = []
            if invoices_data.get("invoices"):
                for inv in invoices_data["invoices"][:3]:  # Get 3 sample invoices
                    invoice_id = inv["invoice_id"]
                    try:
                        # Try Zoho Billing endpoint for full invoice detail
                        invoice_detail_response = await client.get(
                            f"{zoho.base_url}/billing/v1/invoices/{invoice_id}",
                            headers=headers
                        )
                        invoice_detail_response.raise_for_status()
                        invoice_detail = invoice_detail_response.json()
                        invoice_details.append({
                            "invoice_number": inv.get("invoice_number"),
                            "customer_name": inv.get("customer_name"),
                            "total": inv.get("total"),
                            "invoice_date": inv.get("invoice_date"),
                            "detail": invoice_detail
                        })
                    except Exception as e:
                        print(f"Failed to fetch invoice {invoice_id}: {e}")
                        invoice_details.append({
                            "invoice_number": inv.get("invoice_number"),
                            "error": str(e)
                        })

            # Fetch products
            products_response = await client.get(
                f"{zoho.base_url}/billing/v1/products",
                headers=headers,
                params={"filter_by": "ProductStatus.All", "per_page": 10}
            )
            products_response.raise_for_status()
            products_data = products_response.json()

            # Fetch plans
            plans_response = await client.get(
                f"{zoho.base_url}/billing/v1/plans",
                headers=headers,
                params={"filter_by": "PlanStatus.All", "per_page": 10}
            )
            plans_response.raise_for_status()
            plans_data = plans_response.json()

        # Pretty print to console for analysis
        print("\n" + "="*80)
        print("INVOICE DETAILS (with line items)")
        print("="*80)
        print(json.dumps(invoice_details, indent=2))

        print("\n" + "="*80)
        print("PRODUCTS STRUCTURE")
        print("="*80)
        print(json.dumps(products_data, indent=2))

        print("\n" + "="*80)
        print("PLANS STRUCTURE")
        print("="*80)
        print(json.dumps(plans_data, indent=2))

        return {
            "status": "success",
            "message": "Check console for detailed output",
            "summary": {
                "invoices_count": len(invoices_data.get("invoices", [])),
                "products_count": len(products_data.get("products", [])),
                "plans_count": len(plans_data.get("plans", [])),
                "invoice_details": invoice_details,
                "sample_product": products_data.get("products", [{}])[0] if products_data.get("products") else None,
                "sample_plan": plans_data.get("plans", [{}])[0] if plans_data.get("plans") else None,
            }
        }
    except Exception as e:
        import traceback
        error_detail = f"Debug failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/version")
async def version():
    """Version information with git commit hash"""
    import subprocess
    import os

    git_commit = "unknown"
    git_branch = "unknown"

    try:
        # Try to get git commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            git_commit = result.stdout.strip()

        # Try to get git branch
        result_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result_branch.returncode == 0:
            git_branch = result_branch.stdout.strip()
    except Exception as e:
        git_commit = f"error: {str(e)}"

    # Read first few lines of parse_date function to verify fix is in place
    fix_status = "unknown"
    try:
        with open(__file__, 'r') as f:
            content = f.read()
            if 'return dt.replace(tzinfo=None)' in content:
                fix_status = "✅ Timezone fix present"
            else:
                fix_status = "❌ Timezone fix MISSING"
    except:
        pass

    return {
        "app_version": "1.0.0",
        "git_commit": git_commit,
        "git_branch": git_branch,
        "python_version": os.sys.version,
        "timezone_fix": fix_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=settings.port,
        reload=settings.app_env == "dev",
    )

