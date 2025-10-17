"""
Debug what the month-drilldown query returns for September 2025
specifically for invoice 2010783
"""
import asyncio
from datetime import datetime
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def debug_query():
    """Debug the exact query used by month-drilldown endpoint"""

    async with AsyncSessionLocal() as session:
        # Parse target month (same as endpoint)
        year, month_num = 2025, 9
        target_date = datetime(year, month_num, 1)

        print("=" * 80)
        print(f"DEBUGGING MONTH-DRILLDOWN QUERY FOR SEPTEMBER 2025")
        print(f"Target date: {target_date}")
        print("=" * 80)

        # Exact same query as invoices_month_drilldown endpoint
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        ).order_by(Invoice.customer_name, InvoiceLineItem.name)

        result = await session.execute(stmt)
        rows = result.all()

        print(f"\nTotal rows returned: {len(rows)}")

        # Filter for invoice 2010783
        print("\n" + "=" * 80)
        print("ROWS FOR INVOICE 2010783:")
        print("=" * 80)

        invoice_2010783_rows = []
        for line_item, invoice in rows:
            if invoice.invoice_number == "2010783":
                invoice_2010783_rows.append((line_item, invoice))
                print(f"\nInvoice: {invoice.invoice_number}")
                print(f"  Type: {invoice.transaction_type}")
                print(f"  Customer: {invoice.customer_name}")
                print(f"  Product: {line_item.name}")
                print(f"  Period: {line_item.period_start_date} to {line_item.period_end_date}")
                print(f"  Period months: {line_item.period_months}")
                print(f"  Item total: {line_item.item_total} kr")
                print(f"  MRR per month: {line_item.mrr_per_month} kr <-- THIS IS WHAT SHOULD DISPLAY")

        # Also check for CN-02032
        print("\n" + "=" * 80)
        print("ROWS FOR CREDIT NOTE CN-02032:")
        print("=" * 80)

        for line_item, invoice in rows:
            if invoice.invoice_number == "CN-02032":
                print(f"\nCredit Note: {invoice.invoice_number}")
                print(f"  Type: {invoice.transaction_type}")
                print(f"  Customer: {invoice.customer_name}")
                print(f"  Product: {line_item.name}")
                print(f"  Period: {line_item.period_start_date} to {line_item.period_end_date}")
                print(f"  Period months: {line_item.period_months}")
                print(f"  Item total: {line_item.item_total} kr")
                print(f"  MRR per month: {line_item.mrr_per_month} kr")

        # Now simulate the grouping logic
        print("\n" + "=" * 80)
        print("SIMULATING GROUPING LOGIC:")
        print("=" * 80)

        invoices_dict = {}
        creditnotes_list = []

        for line_item, invoice in rows:
            if invoice.invoice_number not in ["2010783", "CN-02032"]:
                continue

            mrr = line_item.mrr_per_month or 0

            item_data = {
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date,
                'customer_name': invoice.customer_name,
                'transaction_type': invoice.transaction_type,
                'item_name': line_item.name,
                'period_start': line_item.period_start_date,
                'period_end': line_item.period_end_date,
                'period_months': line_item.period_months or 1,
                'item_total': line_item.item_total or 0,
                'mrr_per_month': mrr,
                'related_creditnotes': [],
            }

            if invoice.transaction_type == 'invoice':
                # Store invoice for matching
                key = (invoice.customer_name, line_item.name, line_item.period_end_date)
                print(f"\n[INVOICE] {invoice.invoice_number}")
                print(f"  Key: {key}")
                print(f"  MRR: {mrr} kr")
                invoices_dict[key] = item_data
            else:
                # Store credit note for later matching
                print(f"\n[CREDIT NOTE] {invoice.invoice_number}")
                print(f"  MRR: {mrr} kr")
                creditnotes_list.append(item_data)

        # Match credit notes to invoices
        print("\n" + "=" * 80)
        print("MATCHING CREDIT NOTES TO INVOICES:")
        print("=" * 80)

        for cn in creditnotes_list:
            key = (cn['customer_name'], cn['item_name'], cn['period_end'])
            print(f"\nTrying to match {cn['invoice_number']} with key: {key}")

            if key in invoices_dict:
                print(f"  [OK] EXACT MATCH FOUND!")
                invoices_dict[key]['related_creditnotes'].append(cn)
            else:
                print(f"  [NO] No exact match")
                # Try fuzzy matching
                for inv_key, inv_data in invoices_dict.items():
                    if (inv_data['customer_name'] == cn['customer_name'] and
                        inv_data['item_name'] == cn['item_name'] and
                        inv_data['period_end'] and cn['period_end'] and
                        abs((inv_data['period_end'] - cn['period_end']).days) <= 5):
                        print(f"  [OK] FUZZY MATCH FOUND with {inv_data['invoice_number']}")
                        inv_data['related_creditnotes'].append(cn)
                        break

        # Show final invoice data
        print("\n" + "=" * 80)
        print("FINAL DATA THAT WOULD BE SENT TO TEMPLATE:")
        print("=" * 80)

        for key, item in invoices_dict.items():
            print(f"\nInvoice: {item['invoice_number']}")
            print(f"  MRR: {item['mrr_per_month']} kr <-- THIS IS WHAT TEMPLATE RECEIVES")
            print(f"  Related credit notes: {len(item['related_creditnotes'])}")
            for cn in item['related_creditnotes']:
                print(f"    - {cn['invoice_number']}: {cn['mrr_per_month']} kr")

if __name__ == "__main__":
    asyncio.run(debug_query())
