"""
Test the actual grouping logic used in month-drilldown
to see why invoice 2010783 shows as 0 MRR
"""
import asyncio
from datetime import datetime
from sqlalchemy import select
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem

async def test_grouping():
    """Replicate the exact grouping logic from app.py"""

    target_customer = "ACE SJØMAT AS"
    year, month_num = 2025, 9
    target_date = datetime(year, month_num, 1)

    async with AsyncSessionLocal() as session:
        print("=" * 80)
        print(f"TESTING INVOICE GROUPING FOR {target_customer} - SEPTEMBER 2025")
        print("=" * 80)

        # Get all line items active in this month (same query as app.py)
        stmt = select(InvoiceLineItem, Invoice).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).where(
            Invoice.customer_name == target_customer,
            InvoiceLineItem.period_start_date <= target_date,
            InvoiceLineItem.period_end_date >= target_date
        ).order_by(Invoice.customer_name, InvoiceLineItem.name)

        result = await session.execute(stmt)
        rows = result.all()

        print(f"\nTotal rows from query: {len(rows)}")

        # Replicate grouping logic from app.py lines 3745-3809
        from collections import defaultdict

        # First pass: separate invoices and credit notes
        invoices_dict = {}  # key: (customer, product, period) -> invoice data
        creditnotes_list = []  # List of credit notes to match

        total_mrr = 0

        print("\n" + "=" * 80)
        print("FIRST PASS: Separating invoices and credit notes")
        print("=" * 80)

        for line_item, invoice in rows:
            mrr = line_item.mrr_per_month or 0
            total_mrr += mrr

            item_data = {
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date,
                'customer_name': invoice.customer_name,
                'transaction_type': invoice.transaction_type,
                'item_name': line_item.name,
                'item_description': line_item.description or '',
                'vessel_name': line_item.vessel_name or '',
                'call_sign': line_item.call_sign or '',
                'period_start': line_item.period_start_date,
                'period_end': line_item.period_end_date,
                'period_months': line_item.period_months or 1,
                'item_total': line_item.item_total or 0,
                'mrr_per_month': mrr,
                'related_creditnotes': [],  # Will hold matched credit notes
            }

            print(f"\nProcessing: {invoice.invoice_number} ({invoice.transaction_type})")
            print(f"  Product: {line_item.name}")
            print(f"  Period: {line_item.period_start_date} to {line_item.period_end_date}")
            print(f"  MRR: {mrr} NOK")

            if invoice.transaction_type == 'invoice':
                # Store invoice for matching
                key = (invoice.customer_name, line_item.name, line_item.period_end_date)
                print(f"  Storing as INVOICE with key: {key}")
                invoices_dict[key] = item_data
            else:
                # Store credit note for later matching
                print(f"  Storing as CREDIT NOTE for later matching")
                creditnotes_list.append(item_data)

        print("\n" + "=" * 80)
        print("SECOND PASS: Matching credit notes to invoices")
        print("=" * 80)
        print(f"\nInvoices to match against: {len(invoices_dict)}")
        print(f"Credit notes to match: {len(creditnotes_list)}")

        # Second pass: match credit notes to invoices
        unmatched_creditnotes = []
        for cn in creditnotes_list:
            print(f"\n--- Matching Credit Note {cn['invoice_number']} ---")
            print(f"  Product: {cn['item_name']}")
            print(f"  Period end: {cn['period_end']}")
            print(f"  MRR: {cn['mrr_per_month']} NOK")

            # Try to match credit note to invoice
            matched = False
            key = (cn['customer_name'], cn['item_name'], cn['period_end'])
            print(f"  Looking for key: {key}")

            if key in invoices_dict:
                # Exact match found!
                print(f"  [OK] EXACT MATCH FOUND!")
                print(f"  Matched to invoice: {invoices_dict[key]['invoice_number']}")
                invoices_dict[key]['related_creditnotes'].append(cn)
                matched = True
            else:
                print(f"  [X] No exact match, trying fuzzy matching...")
                # Try fuzzy matching: same customer + product, similar period
                for inv_key, inv_data in invoices_dict.items():
                    if (inv_data['customer_name'] == cn['customer_name'] and
                        inv_data['item_name'] == cn['item_name'] and
                        inv_data['period_end'] and cn['period_end']):

                        days_diff = abs((inv_data['period_end'] - cn['period_end']).days)
                        print(f"    Checking invoice {inv_data['invoice_number']}: period_end={inv_data['period_end']}, diff={days_diff} days")

                        if days_diff <= 5:
                            print(f"  [OK] FUZZY MATCH FOUND (within 5 days)!")
                            print(f"  Matched to invoice: {inv_data['invoice_number']}")
                            inv_data['related_creditnotes'].append(cn)
                            matched = True
                            break

            if not matched:
                print(f"  [!] NO MATCH FOUND - will show as unmatched")
                unmatched_creditnotes.append(cn)

        # Build final line_items list: invoices with their credit notes + unmatched credit notes
        line_items = list(invoices_dict.values()) + unmatched_creditnotes

        print("\n" + "=" * 80)
        print("FINAL RESULT: What will be displayed")
        print("=" * 80)

        for item in line_items:
            if item['transaction_type'] == 'invoice':
                print(f"\nINVOICE: {item['invoice_number']}")
                print(f"   Product: {item['item_name']}")
                print(f"   MRR: {item['mrr_per_month']} NOK")
                if item['related_creditnotes']:
                    print(f"   Related credit notes: {len(item['related_creditnotes'])}")
                    for cn in item['related_creditnotes']:
                        print(f"     - {cn['invoice_number']}: {cn['mrr_per_month']} NOK")
                    net_mrr = item['mrr_per_month'] + sum(cn['mrr_per_month'] for cn in item['related_creditnotes'])
                    print(f"   Net MRR (invoice + credit notes): {net_mrr} NOK")
            else:
                print(f"\nUNMATCHED CREDIT NOTE: {item['invoice_number']}")
                print(f"   Product: {item['item_name']}")
                print(f"   MRR: {item['mrr_per_month']} NOK")

        print(f"\n{'='*80}")
        print(f"Total MRR for all items: {total_mrr} NOK")
        print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(test_grouping())
