"""
Incremental invoice synchronization from Zoho Billing API
Only syncs new/modified invoices and credit notes to avoid API limits
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.invoice import Invoice, InvoiceLineItem, InvoiceMRRSnapshot
from services.invoice import InvoiceService
from services.zoho import ZohoClient


class InvoiceSyncService:
    """Service for incremental invoice synchronization"""

    def __init__(self, session: AsyncSession, zoho_client: ZohoClient):
        self.session = session
        self.zoho = zoho_client
        self.invoice_service = InvoiceService(session)

    async def sync_incremental(self, since: Optional[datetime] = None) -> Dict:
        """
        Sync only new/modified invoices and credit notes since last sync

        Args:
            since: Only sync items modified after this date. If None, syncs last 7 days.

        Returns:
            Dict with sync statistics
        """
        if since is None:
            # Default: sync last 7 days to catch any changes
            since = datetime.utcnow() - timedelta(days=7)

        print(f"Starting incremental invoice sync since {since.isoformat()}")

        stats = {
            "invoices_synced": 0,
            "creditnotes_synced": 0,
            "line_items_processed": 0,
            "snapshots_updated": [],
            "errors": []
        }

        try:
            # 1. Sync invoices
            invoice_stats = await self._sync_invoices_since(since)
            stats["invoices_synced"] = invoice_stats["count"]
            stats["line_items_processed"] += invoice_stats["line_items"]

            # 2. Sync credit notes
            cn_stats = await self._sync_creditnotes_since(since)
            stats["creditnotes_synced"] = cn_stats["count"]
            stats["line_items_processed"] += cn_stats["line_items"]

            # 3. Update affected monthly snapshots
            affected_months = await self._get_affected_months(since)
            print(f"\nUpdating {len(affected_months)} affected monthly snapshots...")

            for month_str in affected_months:
                try:
                    await self.invoice_service.generate_monthly_snapshot(month_str)
                    stats["snapshots_updated"].append(month_str)
                    print(f"  ✓ Updated snapshot for {month_str}")
                except Exception as e:
                    error_msg = f"Failed to update snapshot for {month_str}: {str(e)}"
                    print(f"  ✗ {error_msg}")
                    stats["errors"].append(error_msg)

            await self.session.commit()

            print(f"\n{'='*80}")
            print(f"SYNC COMPLETE")
            print(f"{'='*80}")
            print(f"Invoices synced: {stats['invoices_synced']}")
            print(f"Credit notes synced: {stats['creditnotes_synced']}")
            print(f"Line items processed: {stats['line_items_processed']}")
            print(f"Snapshots updated: {len(stats['snapshots_updated'])}")
            if stats['errors']:
                print(f"Errors: {len(stats['errors'])}")

            return stats

        except Exception as e:
            await self.session.rollback()
            raise Exception(f"Invoice sync failed: {str(e)}")

    async def _sync_invoices_since(self, since: datetime) -> Dict:
        """Sync invoices modified since given date"""
        print(f"\nSyncing invoices modified since {since.date()}...")

        import httpx
        headers = await self.zoho._get_headers()
        # Invoices use different organization ID header
        headers['X-com-zoho-invoice-organizationid'] = self.zoho.org_id

        synced_count = 0
        line_items_count = 0

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Fetch invoices (paginated)
            page = 1
            per_page = 200
            has_more = True

            while has_more:
                # Build query params
                params = {
                    "per_page": per_page,
                    "page": page,
                    # Try to filter by date (if API supports it)
                    # Common parameter names: last_modified_time, updated_after, date_from
                    "date_start": since.strftime("%Y-%m-%d")
                }

                response = await client.get(
                    f"{self.zoho.base_url}/billing/v1/invoices",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()

                invoices = data.get("invoices", [])

                if not invoices:
                    break

                # Filter by updated_time in case API doesn't support date filtering
                filtered_invoices = [
                    inv for inv in invoices
                    if self._parse_date(inv.get("updated_time")) >= since
                ]

                print(f"  Page {page}: {len(filtered_invoices)}/{len(invoices)} invoices match filter")

                # Process each invoice
                for inv_data in filtered_invoices:
                    try:
                        invoice_id = inv_data["invoice_id"]

                        # Get full invoice details with line items
                        detail_response = await client.get(
                            f"{self.zoho.base_url}/billing/v1/invoices/{invoice_id}",
                            headers=headers
                        )
                        detail_response.raise_for_status()
                        invoice_detail = detail_response.json().get("invoice", {})

                        # Save invoice and line items
                        line_items = await self._save_invoice(invoice_id, invoice_detail)
                        synced_count += 1
                        line_items_count += line_items

                        # Rate limiting: sleep between requests
                        await asyncio.sleep(0.3)

                    except Exception as e:
                        print(f"    ✗ Error syncing invoice {invoice_id}: {e}")
                        continue

                # Check if there are more pages
                if len(invoices) < per_page:
                    has_more = False
                else:
                    page += 1

                # Commit periodically
                if synced_count % 50 == 0:
                    await self.session.commit()

        print(f"  ✓ Synced {synced_count} invoices with {line_items_count} line items")

        return {
            "count": synced_count,
            "line_items": line_items_count
        }

    async def _sync_creditnotes_since(self, since: datetime) -> Dict:
        """Sync credit notes modified since given date"""
        print(f"\nSyncing credit notes modified since {since.date()}...")

        import httpx
        headers = await self.zoho._get_headers()
        # Credit notes use invoice organization ID header
        headers['X-com-zoho-invoice-organizationid'] = self.zoho.org_id

        synced_count = 0
        line_items_count = 0

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Try credit notes endpoint (similar to invoices)
            try:
                page = 1
                per_page = 200
                has_more = True

                while has_more:
                    params = {
                        "per_page": per_page,
                        "page": page,
                        "date_start": since.strftime("%Y-%m-%d")
                    }

                    response = await client.get(
                        f"{self.zoho.base_url}/billing/v1/creditnotes",
                        headers=headers,
                        params=params
                    )
                    response.raise_for_status()
                    data = response.json()

                    creditnotes = data.get("creditnotes", [])

                    if not creditnotes:
                        break

                    # Filter by updated_time
                    filtered_cns = [
                        cn for cn in creditnotes
                        if self._parse_date(cn.get("updated_time")) >= since
                    ]

                    print(f"  Page {page}: {len(filtered_cns)}/{len(creditnotes)} credit notes match filter")

                    # Process each credit note
                    for cn_data in filtered_cns:
                        try:
                            cn_id = cn_data["creditnote_id"]

                            # Get full credit note details with line items
                            detail_response = await client.get(
                                f"{self.zoho.base_url}/billing/v1/creditnotes/{cn_id}",
                                headers=headers
                            )
                            detail_response.raise_for_status()
                            cn_detail = detail_response.json().get("creditnote", {})

                            # Save credit note as negative invoice
                            line_items = await self._save_creditnote(cn_id, cn_detail)
                            synced_count += 1
                            line_items_count += line_items

                            # Rate limiting
                            await asyncio.sleep(0.3)

                        except Exception as e:
                            print(f"    ✗ Error syncing credit note {cn_id}: {e}")
                            continue

                    if len(creditnotes) < per_page:
                        has_more = False
                    else:
                        page += 1

                    if synced_count % 50 == 0:
                        await self.session.commit()

            except Exception as e:
                print(f"  Note: Could not sync credit notes: {e}")
                print(f"  This is OK if credit notes are included in invoices list")

        print(f"  ✓ Synced {synced_count} credit notes with {line_items_count} line items")

        return {
            "count": synced_count,
            "line_items": line_items_count
        }

    async def _save_invoice(self, invoice_id: str, invoice_detail: Dict) -> int:
        """Save or update invoice and its line items"""

        # Parse dates
        invoice_date = self._parse_date(invoice_detail.get("invoice_date"))
        due_date = self._parse_date(invoice_detail.get("due_date"))
        created_time = self._parse_date(invoice_detail.get("created_time"))
        updated_time = self._parse_date(invoice_detail.get("updated_time"))

        # Check if invoice exists
        invoice = await self.session.get(Invoice, invoice_id)

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
            self.session.add(invoice)

        # Delete existing line items for this invoice
        stmt_delete = delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)
        await self.session.execute(stmt_delete)

        # Create new line items
        line_items = invoice_detail.get("invoice_items", [])
        for item_data in line_items:
            # Calculate MRR from line item
            mrr_calc = self.invoice_service.calculate_mrr_from_line_item(item_data)

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
            self.session.add(line_item)

        return len(line_items)

    async def _save_creditnote(self, cn_id: str, cn_detail: Dict) -> int:
        """Save or update credit note as a negative invoice"""

        # Parse dates
        cn_date = self._parse_date(cn_detail.get("creditnote_date"))
        created_time = self._parse_date(cn_detail.get("created_time"))
        updated_time = self._parse_date(cn_detail.get("updated_time"))

        # Check if credit note exists (stored as invoice)
        invoice = await self.session.get(Invoice, cn_id)

        if invoice:
            # Update existing
            invoice.invoice_number = cn_detail.get("creditnote_number", "")
            invoice.invoice_date = cn_date
            invoice.customer_id = cn_detail.get("customer_id", "")
            invoice.customer_name = cn_detail.get("customer_name", "")
            invoice.customer_email = cn_detail.get("email", "")
            invoice.currency_code = cn_detail.get("currency_code", "NOK")
            invoice.sub_total = -float(cn_detail.get("sub_total", 0))  # Negative!
            invoice.tax_total = -float(cn_detail.get("tax_total", 0))
            invoice.total = -float(cn_detail.get("total", 0))
            invoice.balance = -float(cn_detail.get("balance", 0))
            invoice.status = cn_detail.get("status", "")
            invoice.transaction_type = "creditnote"
            invoice.created_time = created_time
            invoice.updated_time = updated_time
            invoice.last_synced = datetime.utcnow()
        else:
            # Create new
            invoice = Invoice(
                id=cn_id,
                invoice_number=cn_detail.get("creditnote_number", ""),
                invoice_date=cn_date,
                customer_id=cn_detail.get("customer_id", ""),
                customer_name=cn_detail.get("customer_name", ""),
                customer_email=cn_detail.get("email", ""),
                currency_code=cn_detail.get("currency_code", "NOK"),
                sub_total=-float(cn_detail.get("sub_total", 0)),  # Negative!
                tax_total=-float(cn_detail.get("tax_total", 0)),
                total=-float(cn_detail.get("total", 0)),
                balance=-float(cn_detail.get("balance", 0)),
                status=cn_detail.get("status", ""),
                transaction_type="creditnote",
                created_time=created_time,
                updated_time=updated_time,
            )
            self.session.add(invoice)

        # Delete existing line items
        stmt_delete = delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id == cn_id)
        await self.session.execute(stmt_delete)

        # Create new line items (negative amounts)
        line_items = cn_detail.get("creditnote_items", [])
        for item_data in line_items:
            # Calculate MRR from line item
            mrr_calc = self.invoice_service.calculate_mrr_from_line_item(item_data)

            line_item = InvoiceLineItem(
                invoice_id=cn_id,
                item_id=item_data.get("item_id", ""),
                product_id=item_data.get("product_id", ""),
                subscription_id=item_data.get("subscription_id", ""),
                name=item_data.get("name", ""),
                description=item_data.get("description", ""),
                code=item_data.get("code", ""),
                unit=item_data.get("unit", ""),
                price=-float(item_data.get("price", 0)),  # Negative!
                quantity=int(item_data.get("quantity", 1)),
                item_total=-float(item_data.get("item_total", 0)),  # Negative!
                tax_percentage=float(item_data.get("tax_percentage", 0)),
                tax_name=item_data.get("tax_name", ""),
                period_start_date=mrr_calc["period_start_date"],
                period_end_date=mrr_calc["period_end_date"],
                period_months=mrr_calc["period_months"],
                mrr_per_month=-mrr_calc["mrr_per_month"],  # Negative!
            )
            self.session.add(line_item)

        return len(line_items)

    async def _get_affected_months(self, since: datetime) -> List[str]:
        """Get list of months that might be affected by the sync"""
        # Get affected months from invoice line items
        stmt = select(InvoiceLineItem.period_start_date, InvoiceLineItem.period_end_date).distinct()
        result = await self.session.execute(stmt)
        periods = result.all()

        affected_months = set()

        # Add months from since date to now
        current = since.replace(day=1)
        end = datetime.utcnow().replace(day=1)

        while current <= end:
            affected_months.add(current.strftime("%Y-%m"))
            # Add next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return sorted(list(affected_months))

    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string from Zoho API"""
        if not date_str:
            return None
        try:
            if isinstance(date_str, datetime):
                return date_str.replace(tzinfo=None)
            date_str = str(date_str).strip()
            if "T" in date_str:
                # ISO format with timezone
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.replace(tzinfo=None)
            else:
                # Date only
                from dateutil import parser
                dt = parser.parse(date_str)
                return dt.replace(tzinfo=None)
        except Exception as e:
            print(f"Warning: Failed to parse date '{date_str}': {e}")
            return None
