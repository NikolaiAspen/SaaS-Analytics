"""
Deep dive analysis of September 2025 MRR gap
Compares subscription-based MRR vs invoice-based MRR at customer level

Uses month-end snapshot approach (accounting closing date)
"""
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from database import AsyncSessionLocal
from models.subscription import Subscription
from models.invoice import Invoice, InvoiceLineItem

async def analyze_september_gap():
    """
    Analyze MRR gap for September 2025

    Uses "snapshot" approach (end-of-month):
    - Calculates MRR as of Sept 30, 2025 23:59:59
    - Only includes subscriptions/invoices active on that specific date
    - Matches how accounting is done (month-end closing)
    """

    target_month = "2025-09"

    # Calculate month-end date (like accounting month-end closing)
    year, month = 2025, 9
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)

    # Set to end of day
    month_end = month_end.replace(hour=23, minute=59, second=59)

    print("=" * 100)
    print(f"SEPTEMBER 2025 MRR GAP ANALYSIS (Month-End Snapshot)")
    print("=" * 100)
    print(f"Target month: {target_month}")
    print(f"Snapshot date: {month_end} (last day of month)")
    print(f"Method: Accounting month-end closing\n")

    async with AsyncSessionLocal() as session:
        # ===== 1. GET SUBSCRIPTION-BASED MRR =====
        print("\n" + "=" * 100)
        print("1. SUBSCRIPTION-BASED MRR (Active in September 2025)")
        print("=" * 100)

        # Get active subscriptions on Sept 30, 2025
        stmt = select(Subscription).where(
            and_(
                Subscription.status.in_(['live', 'non_renewing']),
                or_(
                    Subscription.activated_at.is_(None),
                    Subscription.activated_at <= month_end
                ),
                or_(
                    Subscription.expires_at.is_(None),
                    Subscription.expires_at >= month_end
                )
            )
        )
        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        print(f"Found {len(subscriptions)} active subscriptions")

        # Calculate MRR for each subscription
        subscription_data = []
        total_sub_mrr = 0

        for sub in subscriptions:
            # Calculate MRR (same logic as MetricsCalculator)
            amount = sub.amount
            interval = sub.interval  # "months" or "years"
            interval_unit = sub.interval_unit  # 1, 2, 3, etc

            # Normalize to monthly
            if interval == "years":
                mrr = (amount / 1.25) / (12 * interval_unit)  # Divide by VAT and years
            else:  # months
                mrr = (amount / 1.25) / interval_unit  # Divide by VAT and months

            total_sub_mrr += mrr

            subscription_data.append({
                'subscription_id': sub.id,
                'customer_id': sub.customer_id,
                'customer_name': sub.customer_name,
                'vessel_name': sub.vessel_name,
                'call_sign': sub.call_sign,
                'plan_name': sub.plan_name,
                'status': sub.status,
                'amount': amount,
                'interval': interval,
                'interval_unit': interval_unit,
                'sub_mrr': mrr
            })

        df_subs = pd.DataFrame(subscription_data)
        print(f"Total Subscription MRR: {total_sub_mrr:,.2f} NOK")
        print(f"\nTop 10 subscriptions by MRR:")
        print(df_subs.nlargest(10, 'sub_mrr')[['customer_name', 'plan_name', 'sub_mrr']])

        # ===== 2. GET INVOICE-BASED MRR =====
        print("\n" + "=" * 100)
        print("2. INVOICE-BASED MRR (Active on Sept 30, 2025 23:59:59)")
        print("=" * 100)

        # Get invoice line items active on month-end date (accounting snapshot)
        stmt = select(InvoiceLineItem).where(
            and_(
                InvoiceLineItem.period_start_date <= month_end,
                InvoiceLineItem.period_end_date >= month_end  # Must still be active on month-end
            )
        )
        result = await session.execute(stmt)
        line_items = result.scalars().all()

        print(f"Found {len(line_items)} active invoice line items (on month-end)")

        # Get invoice details for each line item
        invoice_data = []
        total_inv_mrr = 0

        for item in line_items:
            # Get invoice details
            invoice = await session.get(Invoice, item.invoice_id)

            mrr = item.mrr_per_month if item.mrr_per_month else 0
            total_inv_mrr += mrr

            invoice_data.append({
                'invoice_id': item.invoice_id,
                'line_item_id': item.id,
                'subscription_id': item.subscription_id,
                'customer_id': invoice.customer_id if invoice else None,
                'customer_name': invoice.customer_name if invoice else None,
                'vessel_name': item.vessel_name,
                'call_sign': item.call_sign,
                'item_name': item.name,
                'transaction_type': invoice.transaction_type if invoice else None,
                'item_total': item.item_total,
                'period_months': item.period_months,
                'period_start': item.period_start_date,
                'period_end': item.period_end_date,
                'inv_mrr': mrr
            })

        df_invoices = pd.DataFrame(invoice_data)
        print(f"Total Invoice MRR: {total_inv_mrr:,.2f} NOK")
        print(f"\nTop 10 invoice lines by MRR:")
        print(df_invoices.nlargest(10, 'inv_mrr')[['customer_name', 'item_name', 'inv_mrr']])

        # ===== 3. CALCULATE GAP =====
        print("\n" + "=" * 100)
        print("3. MRR GAP SUMMARY")
        print("=" * 100)
        gap = total_sub_mrr - total_inv_mrr
        gap_pct = (gap / total_sub_mrr * 100) if total_sub_mrr > 0 else 0

        print(f"Subscription MRR: {total_sub_mrr:>15,.2f} NOK")
        print(f"Invoice MRR:      {total_inv_mrr:>15,.2f} NOK")
        print(f"Gap:              {gap:>15,.2f} NOK ({gap_pct:+.2f}%)")

        # ===== 4. MATCH SUBSCRIPTIONS TO INVOICES =====
        print("\n" + "=" * 100)
        print("4. MATCHING SUBSCRIPTIONS TO INVOICES")
        print("=" * 100)

        # Try to match by subscription_id first
        matched_by_sub_id = df_invoices[df_invoices['subscription_id'].notna()].groupby('subscription_id')['inv_mrr'].sum()
        print(f"Matched by subscription_id: {len(matched_by_sub_id)} subscriptions")

        # Match by call_sign (most reliable for vessels)
        df_subs_with_call = df_subs[df_subs['call_sign'].notna()].copy()
        df_invoices_with_call = df_invoices[df_invoices['call_sign'].notna()].copy()

        # Clean call signs for matching
        df_subs_with_call['call_sign_clean'] = df_subs_with_call['call_sign'].str.strip().str.upper()
        df_invoices_with_call['call_sign_clean'] = df_invoices_with_call['call_sign'].str.strip().str.upper()

        # Aggregate invoice MRR by call sign
        inv_by_call = df_invoices_with_call.groupby('call_sign_clean')['inv_mrr'].sum().to_dict()

        # Match subscriptions to invoices
        df_subs_with_call['inv_mrr_matched'] = df_subs_with_call['call_sign_clean'].map(inv_by_call)
        df_subs_with_call['mrr_diff'] = df_subs_with_call['sub_mrr'] - df_subs_with_call['inv_mrr_matched'].fillna(0)

        # ===== 5. IDENTIFY UNMATCHED SUBSCRIPTIONS =====
        print("\n" + "=" * 100)
        print("5. UNMATCHED SUBSCRIPTIONS (Have subscription but no invoice)")
        print("=" * 100)

        unmatched_subs = df_subs_with_call[df_subs_with_call['inv_mrr_matched'].isna() | (df_subs_with_call['inv_mrr_matched'] == 0)]
        print(f"Found {len(unmatched_subs)} unmatched subscriptions")
        unmatched_mrr = unmatched_subs['sub_mrr'].sum()
        print(f"Total unmatched subscription MRR: {unmatched_mrr:,.2f} NOK")

        if len(unmatched_subs) > 0:
            print("\nTop 20 unmatched subscriptions:")
            print(unmatched_subs.nlargest(20, 'sub_mrr')[['customer_name', 'call_sign', 'plan_name', 'sub_mrr']])

        # ===== 6. IDENTIFY LARGE DISCREPANCIES =====
        print("\n" + "=" * 100)
        print("6. LARGE DISCREPANCIES (>1000 NOK difference)")
        print("=" * 100)

        large_diffs = df_subs_with_call[abs(df_subs_with_call['mrr_diff']) > 1000].copy()
        print(f"Found {len(large_diffs)} subscriptions with >1000 NOK difference")

        if len(large_diffs) > 0:
            print("\nTop 20 discrepancies:")
            large_diffs_sorted = large_diffs.reindex(large_diffs['mrr_diff'].abs().sort_values(ascending=False).index)
            print(large_diffs_sorted[['customer_name', 'call_sign', 'plan_name', 'sub_mrr', 'inv_mrr_matched', 'mrr_diff']].head(20))

        # ===== 7. IDENTIFY UNMATCHED INVOICES =====
        print("\n" + "=" * 100)
        print("7. UNMATCHED INVOICES (Have invoice but no subscription)")
        print("=" * 100)

        # Find invoices without matching subscriptions
        sub_call_signs = set(df_subs_with_call['call_sign_clean'].unique())
        unmatched_invs = df_invoices_with_call[~df_invoices_with_call['call_sign_clean'].isin(sub_call_signs)]

        print(f"Found {len(unmatched_invs)} unmatched invoice lines")
        unmatched_inv_mrr = unmatched_invs['inv_mrr'].sum()
        print(f"Total unmatched invoice MRR: {unmatched_inv_mrr:,.2f} NOK")

        if len(unmatched_invs) > 0:
            print("\nTop 20 unmatched invoices:")
            print(unmatched_invs.nlargest(20, 'inv_mrr')[['customer_name', 'call_sign', 'item_name', 'inv_mrr']])

        # ===== 8. SUMMARY OF GAP SOURCES =====
        print("\n" + "=" * 100)
        print("8. GAP BREAKDOWN")
        print("=" * 100)

        print(f"Total gap: {gap:,.2f} NOK ({gap_pct:+.2f}%)")
        print(f"\nSources:")
        print(f"  1. Unmatched subscriptions (no invoice):     {unmatched_mrr:>12,.2f} NOK")
        print(f"  2. Unmatched invoices (no subscription):     {-unmatched_inv_mrr:>12,.2f} NOK")

        # Small differences in matched items
        matched_diffs = df_subs_with_call[df_subs_with_call['inv_mrr_matched'].notna() & (df_subs_with_call['inv_mrr_matched'] > 0)]
        small_diff_sum = matched_diffs['mrr_diff'].sum()
        print(f"  3. Calculation differences (matched items):  {small_diff_sum:>12,.2f} NOK")

        explained_gap = unmatched_mrr - unmatched_inv_mrr + small_diff_sum
        print(f"\nExplained gap: {explained_gap:,.2f} NOK")
        print(f"Unexplained:   {gap - explained_gap:,.2f} NOK")

        # ===== 9. SAVE DETAILED RESULTS =====
        print("\n" + "=" * 100)
        print("9. SAVING RESULTS")
        print("=" * 100)

        # Save full comparison
        df_subs_with_call.to_csv('september_gap_subscriptions.csv', index=False)
        print("Saved: september_gap_subscriptions.csv")

        df_invoices_with_call.to_csv('september_gap_invoices.csv', index=False)
        print("Saved: september_gap_invoices.csv")

        if len(unmatched_subs) > 0:
            unmatched_subs.to_csv('september_gap_unmatched_subs.csv', index=False)
            print("Saved: september_gap_unmatched_subs.csv")

        if len(unmatched_invs) > 0:
            unmatched_invs.to_csv('september_gap_unmatched_invoices.csv', index=False)
            print("Saved: september_gap_unmatched_invoices.csv")

        print("\n" + "=" * 100)
        print("ANALYSIS COMPLETE")
        print("=" * 100)

if __name__ == "__main__":
    asyncio.run(analyze_september_gap())
