import re
from datetime import datetime
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.invoice import Invoice, InvoiceLineItem, InvoiceMRRSnapshot


class InvoiceService:
    """Service for handling invoice-based MRR calculations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def parse_period_from_description(self, description: str, invoice_date: Optional[datetime] = None) -> Tuple[Optional[datetime], Optional[datetime], int]:
        """
        Parse billing period from invoice line item description

        Supports formats:
        - Norwegian: "Gjelder perioden 10 Oct 2025 til 09 Nov 2025"
        - English: "Charges for this duration (from 10-October-2025 to 9-October-2026)"
        - Norwegian alt: "Gjelder fra 1 januar - 31 desember 2022"
        - Dot format: "01.01.22-31.01.22"

        Returns:
            Tuple of (start_date, end_date, months_count)
        """
        if not description:
            return None, None, 1

        try:
            # Pattern 1: Norwegian format "DD MMM YYYY til DD MMM YYYY"
            pattern1 = r'(\d{1,2}\s+\w+\s+\d{4})\s+til\s+(\d{1,2}\s+\w+\s+\d{4})'
            match = re.search(pattern1, description, re.IGNORECASE)

            if match:
                start_str = match.group(1)
                end_str = match.group(2)

                # Parse dates
                start_date = date_parser.parse(start_str, dayfirst=True)
                end_date = date_parser.parse(end_str, dayfirst=True)

                # Calculate months between dates
                months = self._calculate_months_between(start_date, end_date)

                return start_date, end_date, months

            # Pattern 2: English format "(from DD-Month-YYYY to DD-Month-YYYY)"
            pattern2 = r'from\s+(\d{1,2}-\w+-\d{4})\s+to\s+(\d{1,2}-\w+-\d{4})'
            match = re.search(pattern2, description, re.IGNORECASE)

            if match:
                start_str = match.group(1)
                end_str = match.group(2)

                # Parse dates
                start_date = date_parser.parse(start_str, dayfirst=True)
                end_date = date_parser.parse(end_str, dayfirst=True)

                # Calculate months between dates
                months = self._calculate_months_between(start_date, end_date)

                return start_date, end_date, months

            # Pattern 3: "Gjelder fra DD måned - DD måned YYYY"
            pattern3 = r'fra\s+(\d{1,2}\s+\w+)\s*-\s*(\d{1,2}\s+\w+\s+\d{4})'
            match = re.search(pattern3, description, re.IGNORECASE)

            if match:
                start_str_partial = match.group(1)  # e.g. "1 januar"
                end_str = match.group(2)  # e.g. "31 desember 2022"

                end_date = date_parser.parse(end_str, dayfirst=True)
                # Add year from end_date to start_str
                start_str = f"{start_str_partial} {end_date.year}"
                start_date = date_parser.parse(start_str, dayfirst=True)

                months = self._calculate_months_between(start_date, end_date)
                return start_date, end_date, months

            # Pattern 4: Dot format "DD.MM.YY-DD.MM.YY"
            pattern4 = r'(\d{1,2}\.\d{1,2}\.\d{2,4})\s*-\s*(\d{1,2}\.\d{1,2}\.\d{2,4})'
            match = re.search(pattern4, description, re.IGNORECASE)

            if match:
                start_str = match.group(1).replace('.', '-')
                end_str = match.group(2).replace('.', '-')

                start_date = date_parser.parse(start_str, dayfirst=True)
                end_date = date_parser.parse(end_str, dayfirst=True)

                months = self._calculate_months_between(start_date, end_date)
                return start_date, end_date, months

        except Exception as e:
            print(f"Warning: Failed to parse period from description: {description}")
            print(f"  Error: {e}")

        # Fallback: return None and 1 month
        return None, None, 1

    def _calculate_months_between(self, start_date: datetime, end_date: datetime) -> int:
        """
        Calculate number of months between two dates

        Examples:
        - 10 Oct 2025 to 09 Nov 2025 = 1 month
        - 10 Oct 2025 to 09 Oct 2026 = 12 months
        """
        # Calculate difference in months
        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)

        # Add 1 if we're including the end month (e.g., Oct 10 to Nov 9 is 1 full month)
        if end_date.day >= start_date.day:
            months += 1

        # Ensure at least 1 month
        return max(1, months)

    def parse_period_from_name(self, name: str, invoice_date: Optional[datetime] = None) -> Tuple[Optional[datetime], Optional[datetime], int]:
        """
        Parse billing period from product name when description is missing

        Supports formats:
        - "(år)" or "(årlig)" → 12 months
        - "(mnd)" or "(månedlig)" → 1 month

        Args:
            name: Product name (e.g., "Satellittabonnement (år)")
            invoice_date: Invoice date to use as period start (if provided)

        Returns:
            Tuple of (start_date, end_date, months_count)
        """
        if not name:
            return None, None, 1

        name_lower = name.lower()

        # Check for yearly indicators
        if '(år)' in name_lower or '(årlig)' in name_lower or '(årig)' in name_lower:
            months = 12
        # Check for monthly indicators
        elif '(mnd)' in name_lower or '(månedlig)' in name_lower or '(måned)' in name_lower:
            months = 1
        else:
            # No period indicator found
            return None, None, 1

        # If we have invoice_date, calculate period dates
        if invoice_date:
            start_date = invoice_date
            if months > 1:
                # For multi-month periods (yearly, etc)
                end_date = start_date + relativedelta(months=months, days=-1)
            else:
                # For monthly periods: same month as invoice
                end_date = start_date + relativedelta(months=1, days=-1)
            return start_date, end_date, months

        # Return months count without dates
        return None, None, months

    def calculate_mrr_from_line_item(self, line_item_data: Dict) -> Dict:
        """
        Calculate MRR from a single invoice line item

        Args:
            line_item_data: Line item data with keys:
                - description: Line item description (may contain period dates)
                - name: Product name (may contain period indicator like "(år)")
                - price: Line item price (excluding tax)
                - invoice_date: Invoice date (optional, used for calculating period dates from name)

        Returns:
            Dict with MRR calculation details
        """
        description = line_item_data.get("description", "")
        name = line_item_data.get("name", "")
        price = float(line_item_data.get("price", 0))  # Excluding tax
        invoice_date = line_item_data.get("invoice_date")

        # Try parsing period from description first
        start_date, end_date, months = self.parse_period_from_description(description, invoice_date)

        # If description didn't provide dates, try parsing from name
        if start_date is None and name:
            start_date_from_name, end_date_from_name, months_from_name = self.parse_period_from_name(name, invoice_date)
            # Use name-based parsing if it provides dates
            if start_date_from_name is not None:
                start_date = start_date_from_name
                end_date = end_date_from_name
                months = months_from_name

        # Calculate MRR per month
        mrr_per_month = price / months if months > 0 else price

        return {
            "period_start_date": start_date,
            "period_end_date": end_date,
            "period_months": months,
            "mrr_per_month": mrr_per_month,
            "total_price": price
        }

    async def get_mrr_for_month(self, target_month: str) -> float:
        """
        Calculate total MRR for a specific month from all invoice line items

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-10")

        Returns:
            Total MRR for the month
        """
        # Parse target month
        year, month = map(int, target_month.split('-'))
        target_date = datetime(year, month, 1)

        # Get all line items that are active in this month
        stmt = select(InvoiceLineItem).where(
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        )
        result = await self.session.execute(stmt)
        line_items = result.scalars().all()

        # Sum up MRR
        total_mrr = sum(item.mrr_per_month for item in line_items if item.mrr_per_month)

        return total_mrr

    async def get_unique_customers_for_month(self, target_month: str) -> int:
        """
        Count unique customers with active MRR in a specific month

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-10")

        Returns:
            Number of unique customers
        """
        # Parse target month
        year, month = map(int, target_month.split('-'))
        target_date = datetime(year, month, 1)

        # Get all invoices with line items active in this month
        stmt = select(func.count(func.distinct(Invoice.customer_id))).select_from(Invoice).join(
            InvoiceLineItem
        ).where(
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        return count

    async def generate_monthly_snapshot(self, target_month: str) -> InvoiceMRRSnapshot:
        """
        Generate or update MRR snapshot for a specific month

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-10")

        Returns:
            InvoiceMRRSnapshot object
        """
        # Calculate MRR for this month
        mrr = await self.get_mrr_for_month(target_month)
        arr = mrr * 12

        # Count unique customers
        total_customers = await self.get_unique_customers_for_month(target_month)

        # Calculate ARPU
        arpu = mrr / total_customers if total_customers > 0 else 0

        # Count active invoices (invoices with line items active this month)
        year, month = map(int, target_month.split('-'))
        target_date = datetime(year, month, 1)

        stmt = select(func.count(func.distinct(Invoice.id))).select_from(Invoice).join(
            InvoiceLineItem
        ).where(
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        )
        result = await self.session.execute(stmt)
        active_invoices = result.scalar() or 0

        # Check if snapshot exists
        stmt = select(InvoiceMRRSnapshot).where(InvoiceMRRSnapshot.month == target_month)
        result = await self.session.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot:
            # Update existing
            snapshot.mrr = round(mrr, 2)
            snapshot.arr = round(arr, 2)
            snapshot.total_customers = total_customers
            snapshot.active_invoices = active_invoices
            snapshot.arpu = round(arpu, 2)
            snapshot.updated_at = datetime.utcnow()
        else:
            # Create new
            snapshot = InvoiceMRRSnapshot(
                month=target_month,
                mrr=round(mrr, 2),
                arr=round(arr, 2),
                total_customers=total_customers,
                active_invoices=active_invoices,
                arpu=round(arpu, 2),
                source="invoice_calculation"
            )
            self.session.add(snapshot)

        await self.session.commit()
        await self.session.refresh(snapshot)

        return snapshot

    async def get_monthly_trends(self, months: int = 12) -> List[Dict]:
        """
        Get monthly MRR trends from invoice snapshots

        Args:
            months: Number of months to retrieve

        Returns:
            List of monthly trend data
        """
        # Use text-based query to avoid column existence issues
        from sqlalchemy import text

        # Try to get snapshots, handling potential missing columns gracefully
        try:
            stmt = select(InvoiceMRRSnapshot).order_by(InvoiceMRRSnapshot.month.desc()).limit(months)
            result = await self.session.execute(stmt)
            snapshots = result.scalars().all()
        except Exception as e:
            # If columns don't exist, fetch with raw SQL selecting only core columns
            print(f"Warning: Failed to query invoice snapshots (missing columns?): {e}")
            query = text("""
                SELECT id, month, mrr, arr, total_customers, active_invoices,
                       new_mrr, churned_mrr, net_mrr, arpu, source, created_at, updated_at
                FROM invoice_mrr_snapshots
                ORDER BY month DESC
                LIMIT :limit
            """)
            result = await self.session.execute(query, {"limit": months})
            rows = result.fetchall()

            # Convert to snapshot-like objects
            from collections import namedtuple
            Snapshot = namedtuple('Snapshot', ['id', 'month', 'mrr', 'arr', 'total_customers', 'active_invoices',
                                               'new_mrr', 'churned_mrr', 'net_mrr', 'arpu', 'source', 'created_at', 'updated_at'])
            snapshots = [Snapshot(*row) for row in rows]

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
                "active_invoices": snapshot.active_invoices,
                "arpu": snapshot.arpu,
                "new_mrr": snapshot.new_mrr,
                "churned_mrr": snapshot.churned_mrr,
                "net_mrr": snapshot.net_mrr,
                "mrr_change": mrr_change,
                "mrr_change_pct": mrr_change_pct,
                "customer_change": customer_change,
                "active_lines": getattr(snapshot, 'active_lines', 0),
                "invoice_lines": getattr(snapshot, 'invoice_lines', 0),
                "creditnote_lines": getattr(snapshot, 'creditnote_lines', 0),
            })

            prev_mrr = snapshot.mrr
            prev_customers = snapshot.total_customers

        return trends

    async def analyze_mrr_gap(self, target_month: str) -> Dict:
        """
        Analyze the gap between subscription-based and invoice-based MRR

        Returns detailed breakdown of:
        - Customers with invoices but no subscriptions
        - Customers with subscriptions but no invoices
        - Matching statistics (call sign, vessel)

        Args:
            target_month: Month in YYYY-MM format (e.g., "2025-10")

        Returns:
            Dict with gap analysis details
        """
        from models.subscription import Subscription
        from collections import defaultdict

        # Parse target month
        year, month = map(int, target_month.split('-'))
        target_month_start = datetime(year, month, 1)

        # Get last day of month
        if month == 12:
            target_month_end = datetime(year + 1, 1, 1) - relativedelta(days=1)
        else:
            target_month_end = datetime(year, month + 1, 1) - relativedelta(days=1)

        # Get all active subscriptions
        stmt = select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        result = await self.session.execute(stmt)
        subscriptions = result.scalars().all()

        # Build subscription customer lookup by name, call sign, and vessel
        subscription_customers = set()
        sub_by_call_sign = {}
        sub_by_vessel = {}

        for sub in subscriptions:
            subscription_customers.add(sub.customer_name)

            if sub.call_sign:
                call_sign_clean = sub.call_sign.strip().upper()
                if call_sign_clean not in sub_by_call_sign:
                    sub_by_call_sign[call_sign_clean] = []
                sub_by_call_sign[call_sign_clean].append(sub)

            if sub.vessel_name:
                vessel_clean = sub.vessel_name.strip().upper()
                if vessel_clean not in sub_by_vessel:
                    sub_by_vessel[vessel_clean] = []
                sub_by_vessel[vessel_clean].append(sub)

        # Get all invoice line items for target month
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            InvoiceLineItem.period_start_date <= target_month_end,
            InvoiceLineItem.period_end_date >= target_month_start
        )
        result = await self.session.execute(stmt)
        invoice_rows = result.all()

        # Analyze customers with invoices
        invoice_customers = defaultdict(lambda: {
            'total_mrr': 0,
            'vessels': set(),
            'call_signs': set(),
            'line_items': []
        })

        for line_item, invoice in invoice_rows:
            customer_name = invoice.customer_name
            mrr = line_item.mrr_per_month or 0

            invoice_customers[customer_name]['total_mrr'] += mrr

            # Use getattr for optional columns that might not exist in Railway PostgreSQL
            vessel_name = getattr(line_item, 'vessel_name', None)
            call_sign = getattr(line_item, 'call_sign', None)

            if vessel_name:
                invoice_customers[customer_name]['vessels'].add(vessel_name.strip())
            if call_sign:
                invoice_customers[customer_name]['call_signs'].add(call_sign.strip())

            invoice_customers[customer_name]['line_items'].append({
                'item_name': line_item.name,
                'vessel': vessel_name or '',
                'call_sign': call_sign or '',
                'mrr': mrr
            })

        # Find customers with invoices but no subscriptions
        customers_without_subs = []
        matched_by_call_sign = 0
        matched_by_vessel = 0
        unmatched = 0

        total_gap_mrr = 0
        matched_gap_mrr = 0
        unmatched_gap_mrr = 0

        for customer_name, customer_data in invoice_customers.items():
            if customer_name not in subscription_customers:
                # Check if this customer matches by call sign or vessel
                matches = []

                for call_sign in customer_data['call_signs']:
                    call_sign_upper = call_sign.upper()
                    if call_sign_upper in sub_by_call_sign:
                        for sub in sub_by_call_sign[call_sign_upper]:
                            if sub.customer_name not in matches:
                                matches.append({
                                    'type': 'call_sign',
                                    'value': call_sign,
                                    'subscription_customer': sub.customer_name
                                })

                for vessel in customer_data['vessels']:
                    vessel_upper = vessel.upper()
                    if vessel_upper in sub_by_vessel:
                        for sub in sub_by_vessel[vessel_upper]:
                            if sub.customer_name not in [m.get('subscription_customer') for m in matches]:
                                matches.append({
                                    'type': 'vessel',
                                    'value': vessel,
                                    'subscription_customer': sub.customer_name
                                })

                customer_mrr = customer_data['total_mrr']
                total_gap_mrr += customer_mrr

                if matches:
                    matched_gap_mrr += customer_mrr
                    if any(m['type'] == 'call_sign' for m in matches):
                        matched_by_call_sign += 1
                    elif any(m['type'] == 'vessel' for m in matches):
                        matched_by_vessel += 1
                else:
                    unmatched += 1
                    unmatched_gap_mrr += customer_mrr

                customers_without_subs.append({
                    'customer_name': customer_name,
                    'mrr': customer_mrr,
                    'vessels': list(customer_data['vessels']),
                    'call_signs': list(customer_data['call_signs']),
                    'matches': matches,
                    'line_items': customer_data['line_items']
                })

        # Sort by MRR descending
        customers_without_subs.sort(key=lambda x: x['mrr'], reverse=True)

        # Find customers with subscriptions but no invoices (rare, but possible)
        customers_without_invoices = []
        invoice_customer_names = set(invoice_customers.keys())

        for sub in subscriptions:
            if sub.customer_name not in invoice_customer_names:
                interval_months = sub.interval if sub.interval_unit == 'months' else (12 if sub.interval_unit == 'years' else 1)
                mrr = (sub.amount / 1.25) / interval_months if sub.amount else 0

                customers_without_invoices.append({
                    'customer_name': sub.customer_name,
                    'mrr': mrr,
                    'plan_name': sub.plan_name,
                    'vessel_name': sub.vessel_name or '',
                    'call_sign': sub.call_sign or ''
                })

        customers_without_invoices.sort(key=lambda x: x['mrr'], reverse=True)

        return {
            'target_month': target_month,
            'total_gap_mrr': total_gap_mrr,
            'matched_gap_mrr': matched_gap_mrr,
            'unmatched_gap_mrr': unmatched_gap_mrr,
            'customers_without_subscriptions': len(customers_without_subs),
            'customers_without_invoices': len(customers_without_invoices),
            'matched_by_call_sign': matched_by_call_sign,
            'matched_by_vessel': matched_by_vessel,
            'unmatched_customers': unmatched,
            'customers_without_subs_list': customers_without_subs[:30],  # Top 30 by MRR
            'customers_without_invoices_list': customers_without_invoices[:30],  # Top 30 by MRR
        }
