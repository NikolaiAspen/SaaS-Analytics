"""
Analyze Zoho master sales report to understand correct MRR calculation
"""

import pandas as pd
from datetime import datetime
import asyncio
from database import AsyncSessionLocal
from models.invoice import InvoiceLineItem, Invoice
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def analyze_zoho_report():
    """Compare Zoho's report with our calculations"""

    print("="*80)
    print("ZOHO MASTER SALES REPORT ANALYSIS")
    print("="*80)

    # Read Zoho report
    zoho_file = 'c:/Users/nikolai/Downloads/Zoho master sales report pr 30.09.2025.xlsx'

    print("\n[1] READING ZOHO REPORT")
    print("-"*80)

    try:
        # Try reading the Excel file
        df = pd.read_excel(zoho_file)
        print(f"Loaded Zoho report: {len(df)} rows, {len(df.columns)} columns")
        print("\nColumn names:")
        for i, col in enumerate(df.columns):
            print(f"  {i}: {col}")

        print("\nFirst 10 rows:")
        print(df.head(10).to_string())

        print("\nData types:")
        print(df.dtypes)

        # Check if there's subscription vs invoice MRR comparison
        if 'September' in df.columns or 'Sep' in df.columns:
            print("\n[2] SEPTEMBER DATA FOUND")
            print("-"*80)
            # Show September data

        # Look for MRR-related columns
        mrr_cols = [col for col in df.columns if 'mrr' in col.lower() or 'subscription' in col.lower() or 'invoice' in col.lower()]
        if mrr_cols:
            print("\n[3] MRR-RELATED COLUMNS")
            print("-"*80)
            for col in mrr_cols:
                print(f"  {col}")
                if len(df) > 0:
                    print(f"    Sample values: {df[col].head(5).tolist()}")

    except Exception as e:
        print(f"Error reading Zoho report: {e}")

    # Now calculate OUR September MRR
    print("\n\n[4] OUR SEPTEMBER 2025 CALCULATION")
    print("-"*80)

    target_month_start = datetime(2025, 9, 1)
    target_month_end = datetime(2025, 9, 30)

    async with AsyncSessionLocal() as session:
        # Get all line items with periods that overlap September 2025
        result = await session.execute(
            select(InvoiceLineItem)
            .join(Invoice)
            .where(
                InvoiceLineItem.period_start_date.isnot(None),
                InvoiceLineItem.period_end_date.isnot(None),
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
            .options(selectinload(InvoiceLineItem.invoice))
        )
        line_items = result.scalars().all()

        total_mrr = sum(float(item.mrr_per_month or 0) for item in line_items)
        unique_customers = len(set(item.invoice.customer_id for item in line_items))

        print(f"Total Invoice-based MRR (September 2025): {total_mrr:,.2f} NOK")
        print(f"Total Customers: {unique_customers}")
        print(f"Total Line Items: {len(line_items)}")

        # Show breakdown by transaction type
        invoices_mrr = sum(float(item.mrr_per_month or 0) for item in line_items if item.invoice.transaction_type == 'invoice')
        creditnotes_mrr = sum(float(item.mrr_per_month or 0) for item in line_items if item.invoice.transaction_type == 'creditnote')

        print(f"\nBreakdown:")
        print(f"  Invoices MRR: {invoices_mrr:,.2f} NOK")
        print(f"  Credit Notes MRR: {creditnotes_mrr:,.2f} NOK")
        print(f"  Net MRR: {invoices_mrr + creditnotes_mrr:,.2f} NOK")

    # Now calculate OCTOBER for comparison
    print("\n\n[5] OUR OCTOBER 2025 CALCULATION")
    print("-"*80)

    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(InvoiceLineItem)
            .join(Invoice)
            .where(
                InvoiceLineItem.period_start_date.isnot(None),
                InvoiceLineItem.period_end_date.isnot(None),
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
            .options(selectinload(InvoiceLineItem.invoice))
        )
        line_items = result.scalars().all()

        total_mrr = sum(float(item.mrr_per_month or 0) for item in line_items)
        unique_customers = len(set(item.invoice.customer_id for item in line_items))

        print(f"Total Invoice-based MRR (October 2025): {total_mrr:,.2f} NOK")
        print(f"Total Customers: {unique_customers}")
        print(f"Total Line Items: {len(line_items)}")

        # Show breakdown by transaction type
        invoices_mrr = sum(float(item.mrr_per_month or 0) for item in line_items if item.invoice.transaction_type == 'invoice')
        creditnotes_mrr = sum(float(item.mrr_per_month or 0) for item in line_items if item.invoice.transaction_type == 'creditnote')

        print(f"\nBreakdown:")
        print(f"  Invoices MRR: {invoices_mrr:,.2f} NOK")
        print(f"  Credit Notes MRR: {creditnotes_mrr:,.2f} NOK")
        print(f"  Net MRR: {invoices_mrr + creditnotes_mrr:,.2f} NOK")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(analyze_zoho_report())
