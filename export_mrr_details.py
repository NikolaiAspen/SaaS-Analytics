"""
Export detailed MRR breakdown for October 2025
Shows all line items contributing to MRR with full details for review
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def export_mrr_details():
    """Export all line items contributing to October 2025 MRR"""

    target_month = datetime(2025, 10, 1)

    print("="*120)
    print(f"DETAILED MRR BREAKDOWN - OCTOBER 2025")
    print("="*120)

    async with AsyncSessionLocal() as session:
        # Query all line items with period overlapping October 2025
        query = (
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= datetime(2025, 10, 31),
                InvoiceLineItem.period_end_date >= datetime(2025, 10, 1)
            )
            .order_by(Invoice.transaction_type, Invoice.customer_name, InvoiceLineItem.name)
        )

        result = await session.execute(query)
        rows = result.all()

        # Prepare data for display
        data = []
        total_invoice_mrr = 0
        total_creditnote_mrr = 0

        for line_item, invoice in rows:
            mrr = line_item.mrr_per_month or 0

            if invoice.transaction_type == 'invoice':
                total_invoice_mrr += mrr
            else:
                total_creditnote_mrr += mrr

            data.append({
                'Type': 'Invoice' if invoice.transaction_type == 'invoice' else 'Credit Note',
                'Invoice Number': invoice.invoice_number,
                'Invoice Date': invoice.invoice_date.strftime('%Y-%m-%d'),
                'Customer': invoice.customer_name,
                'Item Name': line_item.name,
                'Period Start': line_item.period_start_date.strftime('%Y-%m-%d') if line_item.period_start_date else 'N/A',
                'Period End': line_item.period_end_date.strftime('%Y-%m-%d') if line_item.period_end_date else 'N/A',
                'Period Months': line_item.period_months,
                'Item Total': f"{line_item.item_total:,.2f}",
                'MRR per Month': f"{mrr:,.2f}",
                'Subscription ID': line_item.subscription_id or '',
            })

        # Create DataFrame for nice display
        df = pd.DataFrame(data)

        # Summary statistics
        invoice_count = len(df[df['Type'] == 'Invoice'])
        creditnote_count = len(df[df['Type'] == 'Credit Note'])

        print(f"\nTOTAL LINE ITEMS: {len(df)}")
        print(f"  - Invoices: {invoice_count}")
        print(f"  - Credit Notes: {creditnote_count}")
        print(f"\nTOTAL MRR:")
        print(f"  - From Invoices: {total_invoice_mrr:,.2f} NOK")
        print(f"  - From Credit Notes: {total_creditnote_mrr:,.2f} NOK")
        print(f"  - NET MRR: {total_invoice_mrr + total_creditnote_mrr:,.2f} NOK")

        # Export to Excel for easy review
        output_file = "mrr_breakdown_october_2025.xlsx"
        df.to_excel(output_file, index=False, sheet_name="MRR Details")
        print(f"\n[OK] Exported to {output_file}")

        # Show sample data
        print("\n" + "="*120)
        print("SAMPLE DATA (First 20 rows):")
        print("="*120)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 40)
        print(df.head(20).to_string(index=False))

        # Show credit notes separately
        if creditnote_count > 0:
            print("\n" + "="*120)
            print("ALL CREDIT NOTE ITEMS:")
            print("="*120)
            cn_df = df[df['Type'] == 'Credit Note']
            print(cn_df.to_string(index=False))

        # Show top customers by MRR
        print("\n" + "="*120)
        print("TOP 20 CUSTOMERS BY MRR:")
        print("="*120)

        customer_mrr = {}
        for _, row in df.iterrows():
            customer = row['Customer']
            mrr = float(row['MRR per Month'].replace(',', ''))
            customer_mrr[customer] = customer_mrr.get(customer, 0) + mrr

        top_customers = sorted(customer_mrr.items(), key=lambda x: x[1], reverse=True)[:20]
        for i, (customer, mrr) in enumerate(top_customers, 1):
            print(f"  {i:2d}. {customer:50s} {mrr:12,.2f} NOK")


if __name__ == "__main__":
    asyncio.run(export_mrr_details())
