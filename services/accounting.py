"""
Accounting Service
Handles MRR calculations from accounting's receivable details (ultimate source of truth)
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json
import os

from models.accounting import AccountingReceivableItem, AccountingMRRSnapshot

# Load category mapping from JSON (generated from parameters.xlsx)
CATEGORY_MAPPING = {}
mapping_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'category_mapping.json')
if os.path.exists(mapping_file):
    with open(mapping_file, 'r', encoding='utf-8') as f:
        CATEGORY_MAPPING = json.load(f)


class AccountingService:
    """Service for handling accounting-based MRR calculations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_mrr_for_month(self, target_month: str) -> float:
        """
        Calculate total MRR for a specific month from accounting receivable data

        Uses "snapshot" approach (like subscription MRR):
        - Calculates MRR as of the LAST DAY of the month
        - Only includes items that are ACTIVE on that specific date

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-09")

        Returns:
            Total MRR for the month
        """
        # Parse target month - use LAST DAY of month
        year, month = map(int, target_month.split('-'))

        # Calculate last day of month
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - relativedelta(days=1)

        # Set to end of day (23:59:59)
        month_end = month_end.replace(hour=23, minute=59, second=59)

        # Get all items active on the last day of month
        # Logic: period must have started before month_end AND not yet ended
        stmt = select(AccountingReceivableItem).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        # Sum up MRR - ONLY recurring categories (credit notes will have negative values)
        total_mrr = 0
        for item in items:
            if item.mrr_per_month:
                category = self.categorize_item(item.item_name)
                if self.is_recurring_category(category):
                    total_mrr += item.mrr_per_month

        return total_mrr

    async def get_unique_customers_for_month(self, target_month: str) -> int:
        """
        Count unique customers with active MRR on the last day of a specific month

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-09")

        Returns:
            Number of unique customers
        """
        # Parse target month - use LAST DAY of month
        year, month = map(int, target_month.split('-'))

        # Calculate last day of month
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - relativedelta(days=1)

        month_end = month_end.replace(hour=23, minute=59, second=59)

        # Count unique customers with active items on the last day of month
        stmt = select(func.count(func.distinct(AccountingReceivableItem.customer_name))).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        return count

    async def get_mrr_breakdown_for_month(self, target_month: str) -> Dict:
        """
        Get MRR breakdown (invoice vs creditnote) for a specific month
        Returns BOTH periodized MRR and total invoiced amounts

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-09")

        Returns:
            Dictionary with invoice_mrr, creditnote_mrr, total_invoiced, total_credited
        """
        # Parse target month - use LAST DAY of month
        year, month = map(int, target_month.split('-'))

        # Calculate last day of month
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - relativedelta(days=1)

        month_end = month_end.replace(hour=23, minute=59, second=59)

        # Calculate invoice MRR (periodized)
        stmt = select(
            func.sum(AccountingReceivableItem.mrr_per_month)
        ).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end,
            AccountingReceivableItem.transaction_type == 'invoice'
        )
        result = await self.session.execute(stmt)
        invoice_mrr = result.scalar() or 0

        # Calculate credit note MRR (periodized)
        stmt = select(
            func.sum(AccountingReceivableItem.mrr_per_month)
        ).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end,
            AccountingReceivableItem.transaction_type == 'creditnote'
        )
        result = await self.session.execute(stmt)
        creditnote_mrr = result.scalar() or 0

        # Calculate TOTAL INVOICED amounts (not periodized)
        # This shows the actual invoice amounts sent to customers in this month
        stmt = select(
            func.sum(AccountingReceivableItem.bcy_total_with_tax)
        ).where(
            AccountingReceivableItem.source_month == target_month,
            AccountingReceivableItem.transaction_type == 'invoice'
        )
        result = await self.session.execute(stmt)
        total_invoiced = result.scalar() or 0

        stmt = select(
            func.sum(AccountingReceivableItem.bcy_total_with_tax)
        ).where(
            AccountingReceivableItem.source_month == target_month,
            AccountingReceivableItem.transaction_type == 'creditnote'
        )
        result = await self.session.execute(stmt)
        total_credited = result.scalar() or 0

        return {
            'invoice_mrr': round(invoice_mrr, 2),
            'creditnote_mrr': round(creditnote_mrr, 2),
            'total_invoiced': round(total_invoiced, 2),
            'total_credited': round(total_credited, 2)
        }

    async def generate_monthly_snapshot(self, target_month: str) -> AccountingMRRSnapshot:
        """
        Generate or update MRR snapshot for a specific month from accounting data

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-09")

        Returns:
            AccountingMRRSnapshot object
        """
        # Calculate MRR for this month
        mrr = await self.get_mrr_for_month(target_month)
        arr = mrr * 12

        # Count unique customers
        total_customers = await self.get_unique_customers_for_month(target_month)

        # Calculate ARPU
        arpu = mrr / total_customers if total_customers > 0 else 0

        # Calculate last day of month for all queries
        year, month = map(int, target_month.split('-'))
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - relativedelta(days=1)
        month_end = month_end.replace(hour=23, minute=59, second=59)

        # Count invoice and credit note items
        stmt = select(
            func.count(AccountingReceivableItem.id)
        ).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end,
            AccountingReceivableItem.transaction_type == 'invoice'
        )
        result = await self.session.execute(stmt)
        invoice_items = result.scalar() or 0

        stmt = select(
            func.count(AccountingReceivableItem.id)
        ).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end,
            AccountingReceivableItem.transaction_type == 'creditnote'
        )
        result = await self.session.execute(stmt)
        creditnote_items = result.scalar() or 0

        # Calculate invoice and credit note MRR separately
        stmt = select(
            func.sum(AccountingReceivableItem.mrr_per_month)
        ).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end,
            AccountingReceivableItem.transaction_type == 'invoice'
        )
        result = await self.session.execute(stmt)
        invoice_mrr = result.scalar() or 0

        stmt = select(
            func.sum(AccountingReceivableItem.mrr_per_month)
        ).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end,
            AccountingReceivableItem.transaction_type == 'creditnote'
        )
        result = await self.session.execute(stmt)
        creditnote_mrr = result.scalar() or 0

        # Check if snapshot exists
        stmt = select(AccountingMRRSnapshot).where(AccountingMRRSnapshot.month == target_month)
        result = await self.session.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot:
            # Update existing
            snapshot.mrr = round(mrr, 2)
            snapshot.arr = round(arr, 2)
            snapshot.total_customers = total_customers
            snapshot.arpu = round(arpu, 2)
            snapshot.total_invoice_items = invoice_items
            snapshot.total_creditnote_items = creditnote_items
            snapshot.invoice_mrr = round(invoice_mrr, 2)
            snapshot.creditnote_mrr = round(creditnote_mrr, 2)
            snapshot.updated_at = datetime.utcnow()
        else:
            # Create new
            snapshot = AccountingMRRSnapshot(
                month=target_month,
                mrr=round(mrr, 2),
                arr=round(arr, 2),
                total_customers=total_customers,
                arpu=round(arpu, 2),
                total_invoice_items=invoice_items,
                total_creditnote_items=creditnote_items,
                invoice_mrr=round(invoice_mrr, 2),
                creditnote_mrr=round(creditnote_mrr, 2),
                source="accounting_report"
            )
            self.session.add(snapshot)

        await self.session.commit()
        await self.session.refresh(snapshot)

        return snapshot

    async def get_monthly_trends(self, months: int = 12) -> List[Dict]:
        """
        Get monthly MRR trends from accounting snapshots

        Args:
            months: Number of months to retrieve

        Returns:
            List of monthly trend data
        """
        stmt = select(AccountingMRRSnapshot).order_by(AccountingMRRSnapshot.month.desc()).limit(months)
        result = await self.session.execute(stmt)
        snapshots = result.scalars().all()

        # Reverse to get chronological order
        snapshots = list(reversed(snapshots))

        trends = []
        prev_mrr = None
        prev_customers = None

        for snapshot in snapshots:
            # Parse month for display
            month_date = datetime.strptime(snapshot.month, "%Y-%m")
            month_name = month_date.strftime("%B %Y")

            # Calculate changes
            mrr_change = snapshot.mrr - prev_mrr if prev_mrr is not None else 0
            mrr_change_pct = (mrr_change / prev_mrr * 100) if prev_mrr and prev_mrr > 0 else 0
            customer_change = snapshot.total_customers - prev_customers if prev_customers is not None else 0

            trends.append({
                "month": snapshot.month,
                "month_name": month_name,
                "mrr": snapshot.mrr,
                "arr": snapshot.arr,
                "customers": snapshot.total_customers,
                "arpu": snapshot.arpu,
                "invoice_items": snapshot.total_invoice_items,
                "creditnote_items": snapshot.total_creditnote_items,
                "invoice_mrr": snapshot.invoice_mrr,
                "creditnote_mrr": snapshot.creditnote_mrr,
                "mrr_change": mrr_change,
                "mrr_change_pct": mrr_change_pct,
                "customer_change": customer_change,
            })

            prev_mrr = snapshot.mrr
            prev_customers = snapshot.total_customers

        return trends

    @staticmethod
    def categorize_item(item_name: str) -> str:
        """
        Categorize an accounting item based on parameters.xlsx mapping

        Uses official category mapping from accounting's parameters file.

        Categories from parameters.xlsx:
        - Fangstdagbok (recurring MRR)
        - Support (recurring MRR)
        - VMS (recurring MRR)
        - Sporingstrafikk (recurring MRR)
        - Hardware (one-time)
        - Hardware, mva korr (one-time)
        - Renter og Gebyr Inkasso (one-time)
        - Andre inntekter (one-time)
        - Annet utland uten mva (other)

        Args:
            item_name: The item name from accounting data

        Returns:
            Category name from parameters.xlsx
        """
        if not item_name or item_name.strip() == '':
            return 'Andre inntekter'

        item_name_clean = str(item_name).strip()

        # Try exact match first
        if item_name_clean in CATEGORY_MAPPING:
            return CATEGORY_MAPPING[item_name_clean]

        # Try case-insensitive match
        for mapped_name, category in CATEGORY_MAPPING.items():
            if mapped_name.lower() == item_name_clean.lower():
                return category

        # Default: Andre inntekter
        return 'Andre inntekter'

    @staticmethod
    def is_recurring_category(category: str) -> bool:
        """
        Check if a category represents recurring revenue (MRR)

        Based on parameters.xlsx inntektsgrupper:
        - Recurring: Fangstdagbok, Support, VMS, Sporingstrafikk
        - One-time: Hardware, Hardware mva korr, Renter og Gebyr Inkasso, Andre inntekter
        - Other: Annet utland uten mva
        """
        recurring_categories = [
            'Fangstdagbok',
            'Support',
            'VMS',
            'Sporingstrafikk'
        ]
        return category in recurring_categories

    async def get_category_breakdown(self, target_month: str) -> Dict:
        """
        Get revenue breakdown by category for a specific month

        Args:
            target_month: Month in YYYY-MM format

        Returns:
            Dictionary with category breakdown
        """
        # Calculate last day of month
        year, month = map(int, target_month.split('-'))
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - relativedelta(days=1)
        month_end = month_end.replace(hour=23, minute=59, second=59)

        # Get all items active on last day of month
        stmt = select(AccountingReceivableItem).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        # Categorize and sum
        categories = {}
        total_mrr = 0
        total_revenue = 0

        for item in items:
            category = self.categorize_item(item.item_name)
            mrr = item.mrr_per_month or 0

            if category not in categories:
                categories[category] = {
                    'category': category,
                    'mrr': 0,
                    'count': 0,
                    'is_recurring': self.is_recurring_category(category)
                }

            categories[category]['mrr'] += mrr
            categories[category]['count'] += 1

            # Count toward totals
            total_revenue += mrr
            if self.is_recurring_category(category):
                total_mrr += mrr

        # Convert to list and sort by MRR
        category_list = sorted(categories.values(), key=lambda x: abs(x['mrr']), reverse=True)

        return {
            'month': target_month,
            'categories': category_list,
            'total_mrr': total_mrr,
            'total_revenue': total_revenue,
            'total_one_time': total_revenue - total_mrr
        }

    async def get_category_items(self, target_month: str, category: str) -> Dict:
        """
        Get all items for a specific category in a specific month

        Args:
            target_month: Month in YYYY-MM format
            category: Category name (e.g., "Fangstdagbok", "VMS", "Hardware")

        Returns:
            Dictionary with items and category info
        """
        # Calculate last day of month
        year, month = map(int, target_month.split('-'))
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - relativedelta(days=1)
        month_end = month_end.replace(hour=23, minute=59, second=59)

        # Get all items active on last day of month
        stmt = select(AccountingReceivableItem).where(
            AccountingReceivableItem.period_start_date <= month_end,
            AccountingReceivableItem.period_end_date >= month_end
        )
        result = await self.session.execute(stmt)
        all_items = result.scalars().all()

        # Filter items by category
        category_items = []
        total_mrr = 0

        for item in all_items:
            item_category = self.categorize_item(item.item_name)
            if item_category == category:
                mrr = item.mrr_per_month or 0
                total_mrr += mrr

                category_items.append({
                    'transaction_number': item.transaction_number,
                    'transaction_type': item.transaction_type,
                    'transaction_date': item.transaction_date,
                    'customer_name': item.customer_name,
                    'item_name': item.item_name,
                    'vessel_name': item.vessel_name,
                    'call_sign': item.call_sign,
                    'period_start_date': item.period_start_date,
                    'period_end_date': item.period_end_date,
                    'period_months': item.period_months,
                    'mrr_per_month': mrr,
                    'bcy_total_with_tax': item.bcy_total_with_tax,
                })

        # Sort by MRR descending
        category_items.sort(key=lambda x: abs(x['mrr_per_month']), reverse=True)

        return {
            'month': target_month,
            'category': category,
            'is_recurring': self.is_recurring_category(category),
            'items': category_items,
            'total_mrr': total_mrr,
            'item_count': len(category_items)
        }
