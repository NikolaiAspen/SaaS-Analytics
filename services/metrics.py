import pandas as pd
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.subscription import Subscription


class MetricsCalculator:
    """Calculate SaaS metrics from subscription data"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_mrr(self, as_of_date: datetime = None, debug: bool = False) -> float:
        """
        Calculate Monthly Recurring Revenue

        Args:
            as_of_date: Calculate MRR as of this date (default: now)
            debug: Print detailed debug information

        Returns:
            Total MRR
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        # Check if we're calculating for current time (within last hour)
        is_current = (datetime.utcnow() - as_of_date).total_seconds() < 3600

        if is_current:
            # For current MRR, only include live and non_renewing subscriptions
            stmt = select(Subscription).where(
                Subscription.status.in_(["live", "non_renewing"])
            )
        else:
            # For historical MRR, use date-based filtering
            # Don't filter by current status - a subscription could be "cancelled" now but was "live" then
            stmt = select(Subscription).where(
                Subscription.activated_at <= as_of_date,
                (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > as_of_date)
            )

        result = await self.session.execute(stmt)
        subscriptions = result.scalars().all()

        if debug:
            print(f"\n=== MRR DEBUG INFO (as of {as_of_date}) ===")
            print(f"Total active subscriptions: {len(subscriptions)}")
            print(f"\nFirst 10 subscriptions:")
            for i, sub in enumerate(subscriptions[:10]):
                mrr_value = self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit)
                print(f"{i+1}. ID: {sub.id}")
                print(f"   Customer: {sub.customer_name} ({sub.customer_id})")
                print(f"   Amount: {sub.amount} {sub.currency_code}")
                print(f"   Interval: {sub.interval}, Interval Unit: {sub.interval_unit}")
                print(f"   Normalized MRR: {mrr_value:.2f}")
                print(f"   Status: {sub.status}")
                print(f"   Activated: {sub.activated_at}")
                print(f"   Cancelled: {sub.cancelled_at}")
                print()

        total_mrr = sum(self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit) for sub in subscriptions)

        if debug:
            print(f"TOTAL MRR: {total_mrr:.2f}")
            print("=" * 50 + "\n")

        return round(total_mrr, 2)

    def _normalize_to_mrr(self, amount: float, interval: str, interval_unit: int = 1) -> float:
        """
        Normalize subscription amount to monthly recurring revenue

        IMPORTANT: Zoho stores amounts INCLUSIVE of 25% Norwegian VAT (MVA),
        but MRR should be calculated EXCLUSIVE of VAT. We divide by 1.25 to remove VAT.

        Args:
            amount: Subscription amount (including VAT)
            interval: Billing interval (months, years, etc.)
            interval_unit: Number of interval units

        Returns:
            Monthly amount (excluding VAT)
        """
        # Remove 25% Norwegian VAT (MVA) from amount
        amount_without_vat = amount / 1.25

        if interval == "months":
            return amount_without_vat / interval_unit
        elif interval == "years":
            return amount_without_vat / (interval_unit * 12)
        else:
            # Default to monthly if unknown
            return amount_without_vat

    async def calculate_arr(self, as_of_date: datetime = None) -> float:
        """Calculate Annual Recurring Revenue"""
        mrr = await self.calculate_mrr(as_of_date)
        return round(mrr * 12, 2)

    async def calculate_churn(
        self, start_date: datetime, end_date: datetime
    ) -> Tuple[float, float, int]:
        """
        Calculate customer and revenue churn for a period

        Args:
            start_date: Start of period
            end_date: End of period

        Returns:
            Tuple of (customer_churn_rate, revenue_churn_rate, churned_count)
        """
        # Get customers active at start of period
        stmt_start = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"]),
            Subscription.activated_at <= start_date,
            (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > start_date)
        )
        result_start = await self.session.execute(stmt_start)
        start_subs = result_start.scalars().all()
        start_customer_count = len(set(sub.customer_id for sub in start_subs))
        start_mrr = sum(self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit) for sub in start_subs)

        # Get customers who churned during the period
        # Only count subscriptions that were active at start AND cancelled during period
        stmt_churned = select(Subscription).where(
            Subscription.activated_at < start_date,  # Was active before period started
            Subscription.cancelled_at.between(start_date, end_date)  # Cancelled during period
        )
        result_churned = await self.session.execute(stmt_churned)
        churned_subs = result_churned.scalars().all()
        churned_customer_count = len(set(sub.customer_id for sub in churned_subs))
        churned_mrr = sum(self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit) for sub in churned_subs)

        # Calculate rates
        customer_churn_rate = (churned_customer_count / start_customer_count * 100) if start_customer_count > 0 else 0
        revenue_churn_rate = (churned_mrr / start_mrr * 100) if start_mrr > 0 else 0

        return (
            round(customer_churn_rate, 2),
            round(revenue_churn_rate, 2),
            churned_customer_count
        )

    async def calculate_arpu(self, as_of_date: datetime = None) -> float:
        """
        Calculate Average Revenue Per User

        Args:
            as_of_date: Calculate ARPU as of this date (default: now)

        Returns:
            ARPU value
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        mrr = await self.calculate_mrr(as_of_date)

        stmt = select(Subscription).where(
            Subscription.status == "live",
            Subscription.activated_at <= as_of_date,
            (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > as_of_date)
        )

        result = await self.session.execute(stmt)
        subscriptions = result.scalars().all()
        unique_customers = len(set(sub.customer_id for sub in subscriptions))

        if unique_customers == 0:
            return 0.0

        return round(mrr / unique_customers, 2)

    async def calculate_new_mrr(self, start_date: datetime, end_date: datetime) -> float:
        """
        Calculate MRR from new subscriptions in a period

        Args:
            start_date: Start of period
            end_date: End of period

        Returns:
            New MRR
        """
        stmt = select(Subscription).where(
            Subscription.activated_at.between(start_date, end_date),
            Subscription.status.in_(["live", "non_renewing"])
        )

        result = await self.session.execute(stmt)
        new_subs = result.scalars().all()

        new_mrr = sum(self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit) for sub in new_subs)
        return round(new_mrr, 2)

    async def get_metrics_summary(self, as_of_date: datetime = None) -> Dict:
        """
        Get a comprehensive metrics summary

        Args:
            as_of_date: Calculate metrics as of this date (default: now)

        Returns:
            Dictionary of all key metrics
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        # Calculate current metrics
        mrr = await self.calculate_mrr(as_of_date)
        arr = await self.calculate_arr(as_of_date)
        arpu = await self.calculate_arpu(as_of_date)

        # Get active subscription count
        stmt = select(Subscription).where(
            Subscription.status.in_(["live", "non_renewing"]),
            Subscription.activated_at <= as_of_date,
            (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > as_of_date)
        )
        result = await self.session.execute(stmt)
        active_subs = result.scalars().all()
        active_count = len(active_subs)
        customer_count = len(set(sub.customer_id for sub in active_subs))

        # Calculate churn for last 30 days
        churn_start = as_of_date - timedelta(days=30)
        customer_churn, revenue_churn, churned_count = await self.calculate_churn(churn_start, as_of_date)

        # Calculate new MRR for last 30 days
        new_mrr = await self.calculate_new_mrr(churn_start, as_of_date)

        return {
            "mrr": mrr,
            "arr": arr,
            "arpu": arpu,
            "active_subscriptions": active_count,
            "total_customers": customer_count,
            "customer_churn_rate": customer_churn,
            "revenue_churn_rate": revenue_churn,
            "churned_customers": churned_count,
            "new_mrr": new_mrr,
            "snapshot_date": as_of_date,
        }

    async def get_monthly_trends(self, months: int = 12) -> List[Dict]:
        """
        Get month-over-month trends for key metrics

        Args:
            months: Number of months to look back

        Returns:
            List of monthly metrics with changes
        """
        trends = []
        today = datetime.utcnow()

        for i in range(months):
            # Calculate end of month (last day)
            month_date = today - relativedelta(months=i)
            end_of_month = datetime(month_date.year, month_date.month, 1) + relativedelta(months=1) - timedelta(days=1)
            end_of_month = end_of_month.replace(hour=23, minute=59, second=59)

            # Get metrics for this month
            mrr = await self.calculate_mrr(end_of_month)

            # Get customer and subscription counts
            stmt = select(Subscription).where(
                Subscription.status.in_(["live", "non_renewing"]),
                Subscription.activated_at <= end_of_month,
                (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > end_of_month)
            )
            result = await self.session.execute(stmt)
            active_subs = result.scalars().all()
            customer_count = len(set(sub.customer_id for sub in active_subs))
            subscription_count = len(active_subs)

            # Get new subscriptions this month
            start_of_month = datetime(month_date.year, month_date.month, 1)
            new_mrr = await self.calculate_new_mrr(start_of_month, end_of_month)

            # Get churned subscriptions this month
            # Only count subscriptions that were active at start of month AND cancelled during month
            stmt_churned = select(Subscription).where(
                Subscription.activated_at < start_of_month,  # Was active before this month
                Subscription.cancelled_at.between(start_of_month, end_of_month)  # Cancelled during this month
            )
            result_churned = await self.session.execute(stmt_churned)
            churned_subs = result_churned.scalars().all()
            churned_customers_count = len(set(sub.customer_id for sub in churned_subs))
            churned_mrr = sum(self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit) for sub in churned_subs)

            trends.append({
                "month": month_date.strftime("%Y-%m"),
                "month_name": month_date.strftime("%B %Y"),
                "mrr": round(mrr, 2),
                "customers": customer_count,
                "subscriptions": subscription_count,
                "new_mrr": round(new_mrr, 2),
                "churned_mrr": round(churned_mrr, 2),
                "churned_customers": churned_customers_count,
                "net_mrr": round(new_mrr - churned_mrr, 2),
            })

        # Calculate month-over-month changes
        trends.reverse()  # Oldest first
        for i in range(1, len(trends)):
            prev_month = trends[i-1]
            curr_month = trends[i]

            # Actual MRR change from previous month
            curr_month["mrr_change"] = round(curr_month["mrr"] - prev_month["mrr"], 2)
            curr_month["mrr_change_pct"] = round((curr_month["mrr"] - prev_month["mrr"]) / prev_month["mrr"] * 100, 2) if prev_month["mrr"] > 0 else 0
            curr_month["customer_change"] = curr_month["customers"] - prev_month["customers"]

            # Calculate "Other MRR" (expansion, contraction, reactivations)
            # This is the difference between actual MRR change and net new MRR
            # Other MRR = MRR Change - Net MRR
            curr_month["other_mrr"] = round(curr_month["mrr_change"] - curr_month["net_mrr"], 2)

            # Validate: If Other MRR is very large, there might be data quality issues
            if abs(curr_month["other_mrr"]) > abs(curr_month["mrr_change"]) * 2:
                # This suggests expansion/contraction is larger than net new, which is unusual
                pass

        return trends

    async def save_monthly_snapshot(self, month_str: str, as_of_date: datetime) -> None:
        """
        Save a monthly MRR snapshot for a specific month

        Args:
            month_str: Month in format "YYYY-MM"
            as_of_date: Calculate metrics as of this date (typically end of month)
        """
        from models.subscription import MonthlyMRRSnapshot
        from sqlalchemy import select
        from datetime import timedelta

        # Calculate metrics for this month
        mrr = await self.calculate_mrr(as_of_date)
        arr = mrr * 12

        # Get subscription counts (don't filter by status - use dates only)
        stmt = select(Subscription).where(
            Subscription.activated_at <= as_of_date,
            (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > as_of_date)
        )
        result = await self.session.execute(stmt)
        active_subs = result.scalars().all()
        customer_count = len(set(sub.customer_id for sub in active_subs))
        subscription_count = len(active_subs)

        # Calculate ARPU
        arpu = mrr / customer_count if customer_count > 0 else 0

        # Calculate new and churned MRR for this month
        from dateutil.relativedelta import relativedelta
        month_date = datetime.strptime(month_str, "%Y-%m")
        start_of_month = datetime(month_date.year, month_date.month, 1)
        new_mrr = await self.calculate_new_mrr(start_of_month, as_of_date)

        # Get churned MRR
        stmt_churned = select(Subscription).where(
            Subscription.activated_at < start_of_month,
            Subscription.cancelled_at.between(start_of_month, as_of_date)
        )
        result_churned = await self.session.execute(stmt_churned)
        churned_subs = result_churned.scalars().all()
        churned_mrr = sum(self._normalize_to_mrr(sub.amount, sub.interval, sub.interval_unit) for sub in churned_subs)

        net_mrr = new_mrr - churned_mrr

        # Check if snapshot already exists
        stmt_existing = select(MonthlyMRRSnapshot).where(MonthlyMRRSnapshot.month == month_str)
        result_existing = await self.session.execute(stmt_existing)
        existing_snapshot = result_existing.scalar_one_or_none()

        if existing_snapshot:
            # DO NOT overwrite snapshots from Excel imports
            # Only update if this is the current month (allow auto-updates for ongoing month)
            current_month = datetime.utcnow().strftime("%Y-%m")
            if month_str == current_month:
                # Update current month snapshot
                existing_snapshot.mrr = round(mrr, 2)
                existing_snapshot.arr = round(arr, 2)
                existing_snapshot.total_customers = customer_count
                existing_snapshot.active_subscriptions = subscription_count
                existing_snapshot.new_mrr = round(new_mrr, 2)
                existing_snapshot.churned_mrr = round(churned_mrr, 2)
                existing_snapshot.net_mrr = round(net_mrr, 2)
                existing_snapshot.arpu = round(arpu, 2)
            else:
                # Historical month - don't overwrite Excel data
                print(f"Skipping update for {month_str} - using imported Excel data")
        else:
            # Create new snapshot
            snapshot = MonthlyMRRSnapshot(
                month=month_str,
                mrr=round(mrr, 2),
                arr=round(arr, 2),
                total_customers=customer_count,
                active_subscriptions=subscription_count,
                new_mrr=round(new_mrr, 2),
                churned_mrr=round(churned_mrr, 2),
                net_mrr=round(net_mrr, 2),
                arpu=round(arpu, 2),
                source="calculated",  # Mark as calculated from subscriptions
            )
            self.session.add(snapshot)

        await self.session.commit()

    async def get_monthly_trends_from_snapshots(self, months: int = 12) -> List[Dict]:
        """
        Get month-over-month trends from saved snapshots
        Falls back to calculated trends if snapshots don't exist

        Args:
            months: Number of months to look back

        Returns:
            List of monthly metrics with changes
        """
        from models.subscription import MonthlyMRRSnapshot
        from sqlalchemy import select, desc
        from dateutil.relativedelta import relativedelta

        # Get saved snapshots
        stmt = select(MonthlyMRRSnapshot).order_by(desc(MonthlyMRRSnapshot.month)).limit(months)
        result = await self.session.execute(stmt)
        snapshots = result.scalars().all()

        if not snapshots:
            # No snapshots saved yet, fall back to calculated trends
            return await self.get_monthly_trends(months)

        # Convert snapshots to trends format
        trends = []
        for snapshot in reversed(snapshots):  # Oldest first
            month_date = datetime.strptime(snapshot.month, "%Y-%m")
            # Use the source field to determine if this is from Excel import or calculated
            # Default to "calculated" if source field doesn't exist (for backwards compatibility)
            source = getattr(snapshot, 'source', 'calculated')
            is_from_excel = (source == "excel_import")

            trends.append({
                "month": snapshot.month,
                "month_name": month_date.strftime("%B %Y"),
                "mrr": snapshot.mrr,
                "customers": snapshot.total_customers,
                "subscriptions": snapshot.active_subscriptions,
                "new_mrr": snapshot.new_mrr,
                "churned_mrr": snapshot.churned_mrr,
                "churned_customers": getattr(snapshot, 'churned_customers', 0),
                "net_mrr": snapshot.net_mrr,
                "is_from_excel": is_from_excel,  # True = Excel (100% nøyaktig), False = Estimert fra subscriptions
            })

        # Calculate month-over-month changes
        for i in range(1, len(trends)):
            prev_month = trends[i-1]
            curr_month = trends[i]

            curr_month["mrr_change"] = round(curr_month["mrr"] - prev_month["mrr"], 2)
            curr_month["mrr_change_pct"] = round((curr_month["mrr"] - prev_month["mrr"]) / prev_month["mrr"] * 100, 2) if prev_month["mrr"] > 0 else 0
            curr_month["customer_change"] = curr_month["customers"] - prev_month["customers"]
            curr_month["other_mrr"] = round(curr_month["mrr_change"] - curr_month["net_mrr"], 2)

        return trends
