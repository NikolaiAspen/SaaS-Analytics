"""
Check credit notes for customers without active subscriptions
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def check_creditnotes():
    """Check if customers without subscriptions have credit notes"""

    print("="*120)
    print("CREDIT NOTE ANALYSIS - Customers without active subscriptions")
    print("="*120)

    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        # Get active subscription customers
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()
        subscription_customers = set(sub.customer_name for sub in subscriptions)

        # Get all invoices and credit notes for October 2025
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
            .order_by(Invoice.customer_name, Invoice.transaction_type, Invoice.invoice_date)
        )
        invoice_rows = inv_result.all()

        # Organize by customer
        customers_without_subs = {}

        for line_item, invoice in invoice_rows:
            customer_name = invoice.customer_name

            if customer_name not in subscription_customers:
                if customer_name not in customers_without_subs:
                    customers_without_subs[customer_name] = {
                        'customer_id': invoice.customer_id,
                        'invoices': [],
                        'creditnotes': [],
                        'total_invoice_mrr': 0,
                        'total_creditnote_mrr': 0,
                        'net_mrr': 0
                    }

                mrr = line_item.mrr_per_month or 0

                transaction_info = {
                    'number': invoice.invoice_number,
                    'date': invoice.invoice_date.strftime('%Y-%m-%d'),
                    'item_name': line_item.name,
                    'vessel': line_item.vessel_name or '',
                    'call_sign': line_item.call_sign or '',
                    'mrr': mrr,
                    'item_total': line_item.item_total,
                    'period_start': line_item.period_start_date.strftime('%Y-%m-%d') if line_item.period_start_date else '',
                    'period_end': line_item.period_end_date.strftime('%Y-%m-%d') if line_item.period_end_date else ''
                }

                if invoice.transaction_type == 'invoice':
                    customers_without_subs[customer_name]['invoices'].append(transaction_info)
                    customers_without_subs[customer_name]['total_invoice_mrr'] += mrr
                else:  # creditnote
                    customers_without_subs[customer_name]['creditnotes'].append(transaction_info)
                    customers_without_subs[customer_name]['total_creditnote_mrr'] += mrr

                customers_without_subs[customer_name]['net_mrr'] = (
                    customers_without_subs[customer_name]['total_invoice_mrr'] +
                    customers_without_subs[customer_name]['total_creditnote_mrr']
                )

        # Display results
        print(f"\nFound {len(customers_without_subs)} customers without active subscriptions")
        print("="*120)

        # Separate into categories
        with_creditnotes = []
        without_creditnotes = []

        for customer_name, data in customers_without_subs.items():
            if data['creditnotes']:
                with_creditnotes.append((customer_name, data))
            else:
                without_creditnotes.append((customer_name, data))

        # Sort by net MRR
        with_creditnotes.sort(key=lambda x: x[1]['net_mrr'], reverse=True)
        without_creditnotes.sort(key=lambda x: x[1]['net_mrr'], reverse=True)

        # Display customers WITH credit notes
        print(f"\n[1] CUSTOMERS WITH CREDIT NOTES ({len(with_creditnotes)} customers)")
        print("="*120)

        total_with_cn_net_mrr = 0
        total_with_cn_invoice_mrr = 0
        total_with_cn_creditnote_mrr = 0

        for customer_name, data in with_creditnotes:
            total_with_cn_net_mrr += data['net_mrr']
            total_with_cn_invoice_mrr += data['total_invoice_mrr']
            total_with_cn_creditnote_mrr += data['total_creditnote_mrr']

            print(f"\n{customer_name}")
            print(f"  Net MRR: {data['net_mrr']:,.2f} NOK (Invoices: {data['total_invoice_mrr']:,.2f}, Credit Notes: {data['total_creditnote_mrr']:,.2f})")

            print(f"\n  INVOICES ({len(data['invoices'])}):")
            for inv in data['invoices']:
                print(f"    {inv['number']:15s} {inv['date']} | {inv['item_name']:<40s} | {inv['call_sign']:<10s} | MRR: {inv['mrr']:>10,.2f}")

            print(f"\n  CREDIT NOTES ({len(data['creditnotes'])}):")
            for cn in data['creditnotes']:
                print(f"    {cn['number']:15s} {cn['date']} | {cn['item_name']:<40s} | {cn['call_sign']:<10s} | MRR: {cn['mrr']:>10,.2f}")

        # Display customers WITHOUT credit notes
        print(f"\n{'='*120}")
        print(f"[2] CUSTOMERS WITHOUT CREDIT NOTES ({len(without_creditnotes)} customers)")
        print("="*120)

        total_without_cn_mrr = 0

        for customer_name, data in without_creditnotes:
            total_without_cn_mrr += data['net_mrr']
            print(f"\n{customer_name}")
            print(f"  MRR: {data['net_mrr']:,.2f} NOK")
            print(f"  INVOICES ({len(data['invoices'])}):")
            for inv in data['invoices']:
                print(f"    {inv['number']:15s} {inv['date']} | {inv['item_name']:<40s} | {inv['call_sign']:<10s} | MRR: {inv['mrr']:>10,.2f}")

        # Summary
        print(f"\n{'='*120}")
        print("SUMMARY")
        print("="*120)
        print(f"Customers without active subscriptions: {len(customers_without_subs)}")
        print(f"\n  WITH credit notes: {len(with_creditnotes)} customers")
        print(f"    Invoice MRR: {total_with_cn_invoice_mrr:>15,.2f} NOK")
        print(f"    Credit Note MRR: {total_with_cn_creditnote_mrr:>15,.2f} NOK (negative)")
        print(f"    Net MRR: {total_with_cn_net_mrr:>15,.2f} NOK")
        print(f"\n  WITHOUT credit notes: {len(without_creditnotes)} customers")
        print(f"    Net MRR: {total_without_cn_mrr:>15,.2f} NOK")
        print(f"\n  TOTAL NET MRR: {total_with_cn_net_mrr + total_without_cn_mrr:,.2f} NOK")

        # Check specific example
        print(f"\n{'='*120}")
        print("CHECKING SPECIFIC EXAMPLE: Invoice 2008930 and Credit Note CN-01802")
        print("="*120)

        # Check if we have invoice 2008930
        inv_check = await session.execute(
            select(Invoice).where(Invoice.invoice_number == '2008930')
        )
        inv_2008930 = inv_check.scalar_one_or_none()

        if inv_2008930:
            print(f"✓ Found Invoice 2008930:")
            print(f"  Customer: {inv_2008930.customer_name}")
            print(f"  Date: {inv_2008930.invoice_date.strftime('%Y-%m-%d')}")
            print(f"  Type: {inv_2008930.transaction_type}")
            print(f"  Total: {inv_2008930.total}")
        else:
            print(f"✗ Invoice 2008930 NOT FOUND in database")

        # Check if we have credit note CN-01802
        cn_check = await session.execute(
            select(Invoice).where(Invoice.invoice_number == 'CN-01802')
        )
        cn_01802 = cn_check.scalar_one_or_none()

        if cn_01802:
            print(f"\n✓ Found Credit Note CN-01802:")
            print(f"  Customer: {cn_01802.customer_name}")
            print(f"  Date: {cn_01802.invoice_date.strftime('%Y-%m-%d')}")
            print(f"  Type: {cn_01802.transaction_type}")
            print(f"  Total: {cn_01802.total}")
        else:
            print(f"\n✗ Credit Note CN-01802 NOT FOUND in database")


if __name__ == "__main__":
    asyncio.run(check_creditnotes())
