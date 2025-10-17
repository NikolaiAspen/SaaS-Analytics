"""
DEEP DIVE ANALYSIS - MRR GAP
Analyzes the -5.7% gap between subscription-based and invoice-based MRR
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def deep_dive_gap_analysis():
    """Perform deep dive analysis of MRR gap"""

    target_month_end = datetime(2025, 9, 30, 23, 59, 59)  # September 2025 (complete month)

    print("=" * 120)
    print("DEEP DIVE ANALYSIS - MRR GAP - SEPTEMBER 2025")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        # ===== FETCH SUBSCRIPTION DATA =====
        print("\n[1/4] Loading subscription data...")
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        # Calculate subscription MRR by customer
        sub_mrr_by_customer = {}
        sub_details = {}

        for sub in subscriptions:
            amount = float(sub.amount or 0)
            interval_unit = str(sub.interval_unit or 'months').lower()
            interval_val = sub.interval

            if isinstance(interval_val, str):
                if interval_val.lower() in ['years', 'months']:
                    interval_unit = interval_val.lower()
                    interval = 1
                else:
                    try:
                        interval = int(interval_val)
                    except:
                        interval = 1
            else:
                interval = int(interval_val or 1)

            if interval_unit == 'years':
                mrr = (amount / 1.25) / 12
            elif interval_unit == 'months':
                mrr = (amount / 1.25) / interval
            else:
                mrr = amount / 1.25

            customer_name = sub.customer_name

            if customer_name not in sub_mrr_by_customer:
                sub_mrr_by_customer[customer_name] = 0
                sub_details[customer_name] = []

            sub_mrr_by_customer[customer_name] += mrr
            sub_details[customer_name].append({
                'subscription_id': sub.id,
                'plan': sub.plan_name,
                'status': sub.status,
                'mrr': mrr,
                'created': sub.created_time,
                'vessel': sub.vessel_name or '',
                'call_sign': sub.call_sign or '',
            })

        total_sub_mrr = sum(sub_mrr_by_customer.values())
        print(f"  [OK] {len(subscriptions)} subscriptions")
        print(f"  [OK] {len(sub_mrr_by_customer)} unique customers")
        print(f"  [OK] Total Subscription MRR: {total_sub_mrr:,.2f} NOK")

        # ===== FETCH INVOICE DATA =====
        print("\n[2/4] Loading invoice data...")
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_end
            )
        )
        invoice_rows = inv_result.all()

        # Calculate invoice MRR by customer
        inv_mrr_by_customer = {}
        inv_details = {}

        for line_item, invoice in invoice_rows:
            customer_name = invoice.customer_name
            mrr = line_item.mrr_per_month or 0

            if customer_name not in inv_mrr_by_customer:
                inv_mrr_by_customer[customer_name] = 0
                inv_details[customer_name] = []

            inv_mrr_by_customer[customer_name] += mrr
            inv_details[customer_name].append({
                'invoice_number': invoice.invoice_number,
                'item_name': line_item.name,
                'mrr': mrr,
                'invoice_date': invoice.invoice_date,
                'period_start': line_item.period_start_date,
                'period_end': line_item.period_end_date,
                'transaction_type': invoice.transaction_type,
            })

        total_inv_mrr = sum(inv_mrr_by_customer.values())
        print(f"  [OK] {len(invoice_rows)} invoice line items")
        print(f"  [OK] {len(inv_mrr_by_customer)} unique customers")
        print(f"  [OK] Total Invoice MRR: {total_inv_mrr:,.2f} NOK")

        gap = total_inv_mrr - total_sub_mrr
        gap_pct = (gap / total_sub_mrr * 100) if total_sub_mrr > 0 else 0
        print(f"\n  [!] GAP: {gap:,.2f} NOK ({gap_pct:.2f}%)")

        # ===== CATEGORY 1: CUSTOMERS WITH SUBSCRIPTIONS BUT NO INVOICES =====
        print("\n[3/4] Analyzing customers with subscriptions but no invoices...")

        customers_sub_only = []
        total_sub_only_mrr = 0

        for customer_name, sub_mrr in sub_mrr_by_customer.items():
            inv_mrr = inv_mrr_by_customer.get(customer_name, 0)

            if inv_mrr == 0:  # Has subscription but no invoice
                total_sub_only_mrr += sub_mrr
                customers_sub_only.append({
                    'customer': customer_name,
                    'sub_mrr': sub_mrr,
                    'subscriptions': sub_details[customer_name]
                })

        customers_sub_only.sort(key=lambda x: x['sub_mrr'], reverse=True)

        print(f"\n  CATEGORY 1: Subscriptions without invoices")
        print(f"  Count: {len(customers_sub_only)} customers")
        print(f"  Total MRR: {total_sub_only_mrr:,.2f} NOK")
        print(f"  % of gap: {(total_sub_only_mrr / abs(gap) * 100):.1f}%")

        print("\n  Top 10 customers with subscriptions but no invoices:")
        for i, cust in enumerate(customers_sub_only[:10], 1):
            print(f"  {i}. {cust['customer']}: {cust['sub_mrr']:,.2f} NOK")
            for sub in cust['subscriptions']:
                created_str = sub['created'].strftime('%Y-%m-%d') if sub['created'] else 'Unknown'
                print(f"      - {sub['plan']} (Created: {created_str}, Vessel: {sub['vessel']})")

        # ===== CATEGORY 2: CUSTOMERS WITH INVOICES BUT NO SUBSCRIPTIONS =====
        print("\n[4/4] Analyzing customers with invoices but no subscriptions...")

        customers_inv_only = []
        total_inv_only_mrr = 0

        for customer_name, inv_mrr in inv_mrr_by_customer.items():
            sub_mrr = sub_mrr_by_customer.get(customer_name, 0)

            if sub_mrr == 0:  # Has invoice but no subscription
                total_inv_only_mrr += inv_mrr
                customers_inv_only.append({
                    'customer': customer_name,
                    'inv_mrr': inv_mrr,
                    'invoices': inv_details[customer_name]
                })

        customers_inv_only.sort(key=lambda x: x['inv_mrr'], reverse=True)

        print(f"\n  CATEGORY 2: Invoices without subscriptions")
        print(f"  Count: {len(customers_inv_only)} customers")
        print(f"  Total MRR: {total_inv_only_mrr:,.2f} NOK")
        print(f"  % of gap: {(total_inv_only_mrr / abs(gap) * 100):.1f}%")

        print("\n  Top 10 customers with invoices but no subscriptions:")
        for i, cust in enumerate(customers_inv_only[:10], 1):
            print(f"  {i}. {cust['customer']}: {cust['inv_mrr']:,.2f} NOK")
            for inv in cust['invoices'][:3]:  # Show first 3 invoices
                print(f"      - {inv['item_name']} ({inv['transaction_type']}): {inv['mrr']:,.2f} NOK")

        # ===== CATEGORY 3: CUSTOMERS WITH BOTH BUT DIFFERENT AMOUNTS =====
        print("\n[5/5] Analyzing customers with mismatched MRR...")

        customers_mismatch = []
        total_mismatch = 0

        all_customers = set(sub_mrr_by_customer.keys()) | set(inv_mrr_by_customer.keys())

        for customer_name in all_customers:
            sub_mrr = sub_mrr_by_customer.get(customer_name, 0)
            inv_mrr = inv_mrr_by_customer.get(customer_name, 0)

            # Only customers who have both, but with difference > 5%
            if sub_mrr > 0 and inv_mrr > 0:
                diff = inv_mrr - sub_mrr
                diff_pct = (diff / sub_mrr * 100) if sub_mrr > 0 else 0

                if abs(diff_pct) > 5:  # More than 5% difference
                    total_mismatch += diff
                    customers_mismatch.append({
                        'customer': customer_name,
                        'sub_mrr': sub_mrr,
                        'inv_mrr': inv_mrr,
                        'diff': diff,
                        'diff_pct': diff_pct,
                    })

        customers_mismatch.sort(key=lambda x: abs(x['diff']), reverse=True)

        print(f"\n  CATEGORY 3: Customers with >5% mismatch")
        print(f"  Count: {len(customers_mismatch)} customers")
        print(f"  Total mismatch: {total_mismatch:,.2f} NOK")
        print(f"  % of gap: {(total_mismatch / abs(gap) * 100):.1f}%")

        print("\n  Top 10 customers with largest mismatch:")
        for i, cust in enumerate(customers_mismatch[:10], 1):
            print(f"  {i}. {cust['customer']}")
            print(f"      Subscription MRR: {cust['sub_mrr']:,.2f} NOK")
            print(f"      Invoice MRR:      {cust['inv_mrr']:,.2f} NOK")
            print(f"      Difference:       {cust['diff']:,.2f} NOK ({cust['diff_pct']:.1f}%)")

        # ===== SUMMARY =====
        print("\n" + "=" * 120)
        print("GAP BREAKDOWN SUMMARY")
        print("=" * 120)
        print(f"\nTotal Gap: {gap:,.2f} NOK ({gap_pct:.2f}%)")
        print(f"\nContributing factors:")
        print(f"  1. Subscriptions without invoices:  {total_sub_only_mrr:>12,.2f} NOK ({len(customers_sub_only)} customers)")
        print(f"  2. Invoices without subscriptions:  {total_inv_only_mrr:>12,.2f} NOK ({len(customers_inv_only)} customers)")
        print(f"  3. Mismatched amounts (>5%):        {total_mismatch:>12,.2f} NOK ({len(customers_mismatch)} customers)")
        print(f"\n  Net explained:                      {total_inv_only_mrr - total_sub_only_mrr + total_mismatch:>12,.2f} NOK")
        print(f"  Actual gap:                         {gap:>12,.2f} NOK")
        print("=" * 120)

        # Export to Excel
        print("\n[EXCEL EXPORT] Generating detailed gap analysis report...")

        output_file = "excel/MRR_Gap_Deep_Dive_Analysis_September_2025.xlsx"

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Sheet 1: Summary
            summary_data = {
                'Category': [
                    'Total Subscription MRR',
                    'Total Invoice MRR',
                    'Gap',
                    'Gap %',
                    '',
                    'Breakdown:',
                    '1. Subscriptions without invoices',
                    '2. Invoices without subscriptions',
                    '3. Mismatched amounts (>5%)',
                    '',
                    'Number of customers:',
                    '  - With subscriptions only',
                    '  - With invoices only',
                    '  - With mismatch',
                ],
                'Value': [
                    f"{total_sub_mrr:,.2f} NOK",
                    f"{total_inv_mrr:,.2f} NOK",
                    f"{gap:,.2f} NOK",
                    f"{gap_pct:.2f}%",
                    '',
                    '',
                    f"{total_sub_only_mrr:,.2f} NOK",
                    f"{total_inv_only_mrr:,.2f} NOK",
                    f"{total_mismatch:,.2f} NOK",
                    '',
                    '',
                    len(customers_sub_only),
                    len(customers_inv_only),
                    len(customers_mismatch),
                ],
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

            # Sheet 2: Subscriptions without invoices
            sub_only_data = []
            for cust in customers_sub_only:
                for sub in cust['subscriptions']:
                    sub_only_data.append({
                        'Customer': cust['customer'],
                        'Subscription ID': sub['subscription_id'],
                        'Plan': sub['plan'],
                        'Status': sub['status'],
                        'MRR': sub['mrr'],
                        'Created': sub['created'].strftime('%Y-%m-%d') if sub['created'] else '',
                        'Vessel': sub['vessel'],
                        'Call Sign': sub['call_sign'],
                    })
            pd.DataFrame(sub_only_data).to_excel(writer, sheet_name='Subs Without Invoices', index=False)

            # Sheet 3: Invoices without subscriptions
            inv_only_data = []
            for cust in customers_inv_only:
                for inv in cust['invoices']:
                    inv_only_data.append({
                        'Customer': cust['customer'],
                        'Invoice Number': inv['invoice_number'],
                        'Item Name': inv['item_name'],
                        'Transaction Type': inv['transaction_type'],
                        'MRR': inv['mrr'],
                        'Invoice Date': inv['invoice_date'].strftime('%Y-%m-%d') if inv['invoice_date'] else '',
                        'Period Start': inv['period_start'].strftime('%Y-%m-%d') if inv['period_start'] else '',
                        'Period End': inv['period_end'].strftime('%Y-%m-%d') if inv['period_end'] else '',
                    })
            pd.DataFrame(inv_only_data).to_excel(writer, sheet_name='Invoices Without Subs', index=False)

            # Sheet 4: Mismatched customers
            mismatch_data = []
            for cust in customers_mismatch:
                mismatch_data.append({
                    'Customer': cust['customer'],
                    'Subscription MRR': cust['sub_mrr'],
                    'Invoice MRR': cust['inv_mrr'],
                    'Difference': cust['diff'],
                    'Difference %': cust['diff_pct'],
                })
            pd.DataFrame(mismatch_data).to_excel(writer, sheet_name='Mismatched Amounts', index=False)

        print(f"[SUCCESS] Report saved to: {output_file}")
        print("=" * 120)


if __name__ == "__main__":
    asyncio.run(deep_dive_gap_analysis())
