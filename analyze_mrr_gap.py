"""
Detailed MRR Gap Analysis - Compare subscription-based vs invoice-based MRR
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def analyze_gap():
    """Analyze MRR gap between subscriptions and invoices with multi-tier matching"""

    print("="*120)
    print("MRR GAP ANALYSIS - OCTOBER 2025 (WITH VESSEL MATCHING)")
    print("="*120)

    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        # [1] GET SUBSCRIPTIONS
        print("\n[1] FETCHING SUBSCRIPTIONS")
        print("-"*120)
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        sub_mrr_by_customer = {}
        sub_mrr_by_sub_id = {}
        sub_by_call_sign = {}  # NEW: Index by call sign
        sub_by_vessel_customer = {}  # NEW: Index by vessel + customer
        total_sub_mrr = 0

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
            sub_id = sub.id

            if customer_name not in sub_mrr_by_customer:
                sub_mrr_by_customer[customer_name] = 0
            sub_mrr_by_customer[customer_name] += mrr

            sub_info = {
                'customer': customer_name,
                'mrr': mrr,
                'plan': sub.plan_name,
                'vessel': sub.vessel_name or '',
                'call_sign': sub.call_sign or ''
            }
            sub_mrr_by_sub_id[sub_id] = sub_info

            # NEW: Index by call sign (if exists)
            if sub.call_sign:
                call_sign_clean = sub.call_sign.strip().upper()
                if call_sign_clean not in sub_by_call_sign:
                    sub_by_call_sign[call_sign_clean] = []
                sub_by_call_sign[call_sign_clean].append((sub_id, sub_info))

            # NEW: Index by vessel + customer (if vessel exists)
            if sub.vessel_name:
                vessel_clean = sub.vessel_name.strip().upper()
                vessel_customer_key = f"{vessel_clean}|{customer_name}"
                if vessel_customer_key not in sub_by_vessel_customer:
                    sub_by_vessel_customer[vessel_customer_key] = []
                sub_by_vessel_customer[vessel_customer_key].append((sub_id, sub_info))

            total_sub_mrr += mrr

        print(f"  Subscriptions: {len(subscriptions)}")
        print(f"  Total MRR: {total_sub_mrr:,.2f} NOK")
        print(f"  Customers: {len(sub_mrr_by_customer)}")
        print(f"  Subscriptions with call sign: {len(sub_by_call_sign)}")
        print(f"  Subscriptions with vessel: {len(sub_by_vessel_customer)}")

        # [2] GET INVOICE LINE ITEMS
        print("\n[2] FETCHING INVOICE LINE ITEMS")
        print("-"*120)
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
        )
        invoice_rows = inv_result.all()

        inv_mrr_by_customer = {}
        inv_mrr_by_sub_id = {}
        total_inv_mrr = 0

        for line_item, invoice in invoice_rows:
            mrr = line_item.mrr_per_month or 0
            customer_name = invoice.customer_name
            sub_id = line_item.subscription_id

            if customer_name not in inv_mrr_by_customer:
                inv_mrr_by_customer[customer_name] = 0
            inv_mrr_by_customer[customer_name] += mrr

            if sub_id:
                if sub_id not in inv_mrr_by_sub_id:
                    inv_mrr_by_sub_id[sub_id] = 0
                inv_mrr_by_sub_id[sub_id] += mrr

            total_inv_mrr += mrr

        print(f"  Invoice line items: {len(invoice_rows)}")
        print(f"  Total MRR: {total_inv_mrr:,.2f} NOK")
        print(f"  Customers: {len(inv_mrr_by_customer)}")

        # [3] CUSTOMER COMPARISON
        print("\n[3] CUSTOMER COMPARISON")
        print("-"*120)
        all_customers = set(sub_mrr_by_customer.keys()) | set(inv_mrr_by_customer.keys())
        only_in_subs = set(sub_mrr_by_customer.keys()) - set(inv_mrr_by_customer.keys())
        only_in_invoices = set(inv_mrr_by_customer.keys()) - set(sub_mrr_by_customer.keys())

        only_subs_mrr = sum(sub_mrr_by_customer.get(c, 0) for c in only_in_subs)
        only_inv_mrr = sum(inv_mrr_by_customer.get(c, 0) for c in only_in_invoices)

        print(f"  Total unique customers: {len(all_customers)}")
        print(f"  Only in subscriptions: {len(only_in_subs)} ({only_subs_mrr:,.2f} NOK)")
        print(f"  Only in invoices: {len(only_in_invoices)} ({only_inv_mrr:,.2f} NOK)")

        # [4] TOP GAPS
        print("\n[4] TOP 20 CUSTOMERS WITH LARGEST GAPS")
        print("-"*120)
        gap_customers = []
        for customer in all_customers:
            sub_mrr = sub_mrr_by_customer.get(customer, 0)
            inv_mrr = inv_mrr_by_customer.get(customer, 0)
            diff = inv_mrr - sub_mrr
            if abs(diff) > 0.01:
                gap_customers.append({'customer': customer, 'sub_mrr': sub_mrr, 'inv_mrr': inv_mrr, 'diff': diff})

        gap_customers.sort(key=lambda x: abs(x['diff']), reverse=True)

        print(f"{'Customer':<50} {'Sub MRR':>15} {'Inv MRR':>15} {'Diff':>15}")
        print("-"*120)
        for item in gap_customers[:20]:
            print(f"{item['customer']:<50} {item['sub_mrr']:>15,.2f} {item['inv_mrr']:>15,.2f} {item['diff']:>15,.2f}")

        # [5] MULTI-TIER MATCHING: SUBSCRIPTION ID, CALL SIGN, VESSEL
        print("\n[5] MULTI-TIER MATCHING ANALYSIS")
        print("-"*120)

        # Track matched subscriptions
        matched_by_sub_id = set()
        matched_by_call_sign = set()
        matched_by_vessel = set()

        # Tier 1: Match by subscription_id
        for sub_id in inv_mrr_by_sub_id.keys():
            if sub_id in sub_mrr_by_sub_id:
                matched_by_sub_id.add(sub_id)

        # Tier 2: Match by call sign (for unmatched subscriptions)
        for line_item, invoice in invoice_rows:
            if line_item.call_sign:
                call_sign_clean = line_item.call_sign.strip().upper()
                if call_sign_clean in sub_by_call_sign:
                    # Found matching call sign in subscriptions
                    for sub_id, sub_info in sub_by_call_sign[call_sign_clean]:
                        if sub_id not in matched_by_sub_id:  # Only if not already matched
                            # Verify customer name also matches
                            if invoice.customer_name == sub_info['customer']:
                                matched_by_call_sign.add(sub_id)

        # Tier 3: Match by vessel + customer (for still unmatched)
        for line_item, invoice in invoice_rows:
            if line_item.vessel_name:
                vessel_clean = line_item.vessel_name.strip().upper()
                vessel_customer_key = f"{vessel_clean}|{invoice.customer_name}"
                if vessel_customer_key in sub_by_vessel_customer:
                    for sub_id, sub_info in sub_by_vessel_customer[vessel_customer_key]:
                        if sub_id not in matched_by_sub_id and sub_id not in matched_by_call_sign:
                            matched_by_vessel.add(sub_id)

        # Calculate MRR for each tier
        mrr_matched_sub_id = sum(sub_mrr_by_sub_id[sid]['mrr'] for sid in matched_by_sub_id)
        mrr_matched_call_sign = sum(sub_mrr_by_sub_id[sid]['mrr'] for sid in matched_by_call_sign)
        mrr_matched_vessel = sum(sub_mrr_by_sub_id[sid]['mrr'] for sid in matched_by_vessel)

        # Unmatched subscriptions
        all_matched = matched_by_sub_id | matched_by_call_sign | matched_by_vessel
        unmatched_subs = []
        for sub_id, sub_info in sub_mrr_by_sub_id.items():
            if sub_id not in all_matched:
                unmatched_subs.append({
                    'sub_id': sub_id,
                    'customer': sub_info['customer'],
                    'mrr': sub_info['mrr'],
                    'plan': sub_info['plan'],
                    'vessel': sub_info['vessel'],
                    'call_sign': sub_info['call_sign']
                })

        unmatched_subs.sort(key=lambda x: x['mrr'], reverse=True)
        mrr_unmatched = sum(s['mrr'] for s in unmatched_subs)

        print(f"  Matching Results:")
        print(f"    Tier 1 - By Subscription ID: {len(matched_by_sub_id):4d} ({mrr_matched_sub_id:12,.2f} NOK)")
        print(f"    Tier 2 - By Call Sign:       {len(matched_by_call_sign):4d} ({mrr_matched_call_sign:12,.2f} NOK)")
        print(f"    Tier 3 - By Vessel+Customer: {len(matched_by_vessel):4d} ({mrr_matched_vessel:12,.2f} NOK)")
        print(f"    {'-'*70}")
        print(f"    Total Matched:                {len(all_matched):4d} ({mrr_matched_sub_id + mrr_matched_call_sign + mrr_matched_vessel:12,.2f} NOK)")
        print(f"    Still Unmatched:              {len(unmatched_subs):4d} ({mrr_unmatched:12,.2f} NOK)")

        if unmatched_subs[:20]:
            print(f"\n  TOP 20 UNMATCHED SUBSCRIPTIONS:")
            print(f"  {'Customer':<35} {'Plan':<30} {'Vessel':<15} {'Call Sign':<10} {'MRR':>12}")
            print(f"  {'-'*110}")
            for item in unmatched_subs[:20]:
                print(f"  {item['customer']:<35} {item['plan']:<30} {item['vessel']:<15} {item['call_sign']:<10} {item['mrr']:>12,.2f}")

        # [6] SUMMARY
        print("\n" + "="*120)
        print("SUMMARY WITH MULTI-TIER MATCHING")
        print("="*120)
        print(f"Subscription-based MRR: {total_sub_mrr:,.2f} NOK")
        print(f"Invoice-based MRR:     {total_inv_mrr:,.2f} NOK")
        print(f"Total gap:             {total_inv_mrr - total_sub_mrr:,.2f} NOK ({((total_inv_mrr - total_sub_mrr) / total_sub_mrr * 100):.1f}%)")
        print(f"\nMatching breakdown:")
        print(f"  Matched by Subscription ID:  {len(matched_by_sub_id):4d} subs ({mrr_matched_sub_id:12,.2f} NOK)")
        print(f"  Matched by Call Sign:        {len(matched_by_call_sign):4d} subs ({mrr_matched_call_sign:12,.2f} NOK)")
        print(f"  Matched by Vessel+Customer:  {len(matched_by_vessel):4d} subs ({mrr_matched_vessel:12,.2f} NOK)")
        print(f"  {'-'*80}")
        print(f"  Total Matched:               {len(all_matched):4d} subs ({mrr_matched_sub_id + mrr_matched_call_sign + mrr_matched_vessel:12,.2f} NOK)")
        print(f"  Still Unmatched:             {len(unmatched_subs):4d} subs ({mrr_unmatched:12,.2f} NOK)")
        print(f"\nGap contributors:")
        print(f"  1. Unmatched subscriptions: -{mrr_unmatched:,.2f} NOK ({len(unmatched_subs)} subs)")
        print(f"  2. Customers only in invoices: +{only_inv_mrr:,.2f} NOK ({len(only_in_invoices)} customers)")
        print(f"  3. Amount differences in matched: {(total_inv_mrr - total_sub_mrr) - (only_inv_mrr - mrr_unmatched):,.2f} NOK")


if __name__ == "__main__":
    asyncio.run(analyze_gap())
