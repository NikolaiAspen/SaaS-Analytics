"""
Export customers with invoices in October 2025 but no active subscriptions
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def export_customers_no_subs():
    """Export customers with invoices but no active subscriptions"""

    print("="*120)
    print("CUSTOMERS WITH INVOICES BUT NO ACTIVE SUBSCRIPTIONS - OCTOBER 2025")
    print("="*120)

    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        # Get all active subscriptions
        print("\n[1] Fetching active subscriptions...")
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        subscription_customers = set(sub.customer_name for sub in subscriptions)
        print(f"  Active subscription customers: {len(subscription_customers)}")

        # Get all invoice line items for October 2025
        print("\n[2] Fetching invoice line items for October 2025...")
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
            .order_by(Invoice.customer_name, Invoice.invoice_date)
        )
        invoice_rows = inv_result.all()
        print(f"  Invoice line items: {len(invoice_rows)}")

        # Find customers with invoices but no subscriptions
        invoice_customers = {}
        for line_item, invoice in invoice_rows:
            customer_name = invoice.customer_name
            if customer_name not in invoice_customers:
                invoice_customers[customer_name] = {
                    'customer_id': invoice.customer_id,
                    'customer_name': customer_name,
                    'total_mrr': 0,
                    'line_items': []
                }

            mrr = line_item.mrr_per_month or 0
            invoice_customers[customer_name]['total_mrr'] += mrr
            invoice_customers[customer_name]['line_items'].append({
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
                'transaction_type': invoice.transaction_type,
                'item_name': line_item.name,
                'item_code': line_item.code,
                'vessel_name': line_item.vessel_name or '',
                'call_sign': line_item.call_sign or '',
                'subscription_id': line_item.subscription_id or '',
                'period_start': line_item.period_start_date.strftime('%Y-%m-%d') if line_item.period_start_date else '',
                'period_end': line_item.period_end_date.strftime('%Y-%m-%d') if line_item.period_end_date else '',
                'period_months': line_item.period_months,
                'item_total': line_item.item_total,
                'mrr': mrr
            })

        # Filter to customers without active subscriptions
        customers_no_subs = {
            name: data for name, data in invoice_customers.items()
            if name not in subscription_customers
        }

        print(f"\n[3] Found {len(customers_no_subs)} customers with invoices but no active subscriptions")

        # Prepare data for export
        export_data = []
        for customer_name, customer_data in sorted(customers_no_subs.items(), key=lambda x: x[1]['total_mrr'], reverse=True):
            for line_item in customer_data['line_items']:
                export_data.append({
                    'Customer Name': customer_name,
                    'Customer ID': customer_data['customer_id'],
                    'Total MRR': f"{customer_data['total_mrr']:.2f}",
                    'Invoice Number': line_item['invoice_number'],
                    'Invoice Date': line_item['invoice_date'],
                    'Type': 'Invoice' if line_item['transaction_type'] == 'invoice' else 'Credit Note',
                    'Item Name': line_item['item_name'],
                    'Item Code': line_item['item_code'],
                    'Vessel Name': line_item['vessel_name'],
                    'Call Sign': line_item['call_sign'],
                    'Subscription ID': line_item['subscription_id'],
                    'Period Start': line_item['period_start'],
                    'Period End': line_item['period_end'],
                    'Period Months': line_item['period_months'],
                    'Item Total': f"{line_item['item_total']:.2f}",
                    'MRR': f"{line_item['mrr']:.2f}"
                })

        # Export to Excel
        df = pd.DataFrame(export_data)
        output_file = "customers_no_subscriptions_oct2025.xlsx"
        df.to_excel(output_file, index=False, sheet_name="No Active Subs")
        print(f"\n[OK] Exported to {output_file}")

        # Summary statistics
        total_mrr = sum(c['total_mrr'] for c in customers_no_subs.values())
        print(f"\n{'='*120}")
        print(f"SUMMARY")
        print(f"{'='*120}")
        print(f"Customers with invoices but no active subscriptions: {len(customers_no_subs)}")
        print(f"Total MRR from these customers: {total_mrr:,.2f} NOK")
        print(f"Average MRR per customer: {total_mrr/len(customers_no_subs):,.2f} NOK")

        # Show top 30
        print(f"\n{'='*120}")
        print(f"TOP 30 CUSTOMERS (by MRR):")
        print(f"{'='*120}")
        print(f"{'Customer Name':<50} {'Customer ID':<20} {'MRR':>15} {'Line Items':>12}")
        print("-"*120)

        sorted_customers = sorted(customers_no_subs.items(), key=lambda x: x[1]['total_mrr'], reverse=True)
        for i, (customer_name, customer_data) in enumerate(sorted_customers[:30], 1):
            print(f"{i:2d}. {customer_name:<47} {customer_data['customer_id']:<20} {customer_data['total_mrr']:>15,.2f} {len(customer_data['line_items']):>12}")

        # Show all customers (compact list)
        print(f"\n{'='*120}")
        print(f"ALL {len(customers_no_subs)} CUSTOMERS (alphabetical):")
        print(f"{'='*120}")
        sorted_alpha = sorted(customers_no_subs.items(), key=lambda x: x[0])
        for customer_name, customer_data in sorted_alpha:
            print(f"  {customer_name:<70} {customer_data['total_mrr']:>12,.2f} NOK")


if __name__ == "__main__":
    asyncio.run(export_customers_no_subs())
