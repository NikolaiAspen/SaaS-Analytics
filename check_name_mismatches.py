"""
Check for customers with invoices but no subscriptions that might be name mismatches
by comparing vessel names and call signs
"""

import asyncio
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def check_name_mismatches():
    """Find potential name mismatches by comparing vessel/call sign data"""

    print("="*120)
    print("NAME MISMATCH ANALYSIS - Customers with invoices but no subscriptions")
    print("="*120)

    target_month_start = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31)

    async with AsyncSessionLocal() as session:
        # Get all active subscriptions with vessel/call sign data
        print("\n[1] Fetching subscriptions with vessel/call sign...")
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        # Index subscriptions by call sign and vessel
        sub_by_call_sign = {}
        sub_by_vessel = {}
        subscription_customers = set()

        for sub in subscriptions:
            subscription_customers.add(sub.customer_name)

            if sub.call_sign:
                call_sign_clean = sub.call_sign.strip().upper()
                if call_sign_clean not in sub_by_call_sign:
                    sub_by_call_sign[call_sign_clean] = []
                sub_by_call_sign[call_sign_clean].append({
                    'customer_name': sub.customer_name,
                    'plan_name': sub.plan_name,
                    'vessel_name': sub.vessel_name or '',
                    'call_sign': sub.call_sign,
                    'amount': sub.amount
                })

            if sub.vessel_name:
                vessel_clean = sub.vessel_name.strip().upper()
                if vessel_clean not in sub_by_vessel:
                    sub_by_vessel[vessel_clean] = []
                sub_by_vessel[vessel_clean].append({
                    'customer_name': sub.customer_name,
                    'plan_name': sub.plan_name,
                    'vessel_name': sub.vessel_name,
                    'call_sign': sub.call_sign or '',
                    'amount': sub.amount
                })

        print(f"  Subscriptions: {len(subscriptions)}")
        print(f"  Unique call signs: {len(sub_by_call_sign)}")
        print(f"  Unique vessels: {len(sub_by_vessel)}")

        # Get invoice line items for October 2025
        print("\n[2] Fetching invoice line items...")
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_start
            )
        )
        invoice_rows = inv_result.all()

        # Find invoices from customers without subscriptions
        invoice_customers = {}
        for line_item, invoice in invoice_rows:
            customer_name = invoice.customer_name
            if customer_name not in subscription_customers:
                if customer_name not in invoice_customers:
                    invoice_customers[customer_name] = {
                        'total_mrr': 0,
                        'vessels': set(),
                        'call_signs': set(),
                        'line_items': []
                    }

                mrr = line_item.mrr_per_month or 0
                invoice_customers[customer_name]['total_mrr'] += mrr

                if line_item.vessel_name:
                    invoice_customers[customer_name]['vessels'].add(line_item.vessel_name.strip().upper())
                if line_item.call_sign:
                    invoice_customers[customer_name]['call_signs'].add(line_item.call_sign.strip().upper())

                invoice_customers[customer_name]['line_items'].append({
                    'item_name': line_item.name,
                    'vessel': line_item.vessel_name or '',
                    'call_sign': line_item.call_sign or '',
                    'mrr': mrr
                })

        print(f"  Customers with invoices but no subscriptions: {len(invoice_customers)}")

        # Find potential matches
        print("\n[3] Finding potential name mismatches...")
        print("="*120)

        matches_found = []
        no_match = []

        for invoice_customer, customer_data in invoice_customers.items():
            found_match = False
            matches = []

            # Check call signs
            for call_sign in customer_data['call_signs']:
                if call_sign in sub_by_call_sign:
                    for sub_info in sub_by_call_sign[call_sign]:
                        if sub_info['customer_name'] != invoice_customer:
                            matches.append({
                                'match_type': 'Call Sign',
                                'match_value': call_sign,
                                'subscription_customer': sub_info['customer_name'],
                                'subscription_plan': sub_info['plan_name'],
                                'subscription_vessel': sub_info['vessel_name']
                            })
                            found_match = True

            # Check vessels
            for vessel in customer_data['vessels']:
                if vessel in sub_by_vessel:
                    for sub_info in sub_by_vessel[vessel]:
                        if sub_info['customer_name'] != invoice_customer:
                            # Avoid duplicate matches
                            already_matched = any(
                                m['subscription_customer'] == sub_info['customer_name']
                                for m in matches
                            )
                            if not already_matched:
                                matches.append({
                                    'match_type': 'Vessel',
                                    'match_value': vessel,
                                    'subscription_customer': sub_info['customer_name'],
                                    'subscription_plan': sub_info['plan_name'],
                                    'subscription_vessel': sub_info['vessel_name']
                                })
                                found_match = True

            if found_match:
                matches_found.append({
                    'invoice_customer': invoice_customer,
                    'invoice_mrr': customer_data['total_mrr'],
                    'invoice_vessels': customer_data['vessels'],
                    'invoice_call_signs': customer_data['call_signs'],
                    'matches': matches
                })
            else:
                no_match.append({
                    'invoice_customer': invoice_customer,
                    'invoice_mrr': customer_data['total_mrr'],
                    'invoice_vessels': customer_data['vessels'],
                    'invoice_call_signs': customer_data['call_signs']
                })

        # Display results
        print(f"\nFOUND {len(matches_found)} POTENTIAL NAME MISMATCHES:")
        print("="*120)

        matches_found.sort(key=lambda x: x['invoice_mrr'], reverse=True)

        total_matched_mrr = 0
        for item in matches_found:
            total_matched_mrr += item['invoice_mrr']
            print(f"\n{'='*120}")
            print(f"INVOICE CUSTOMER: {item['invoice_customer']}")
            print(f"  Invoice MRR: {item['invoice_mrr']:,.2f} NOK")
            print(f"  Vessels: {', '.join(item['invoice_vessels']) if item['invoice_vessels'] else 'N/A'}")
            print(f"  Call Signs: {', '.join(item['invoice_call_signs']) if item['invoice_call_signs'] else 'N/A'}")
            print(f"\n  MATCHES TO SUBSCRIPTIONS:")
            for match in item['matches']:
                print(f"    ➜ {match['subscription_customer']}")
                print(f"      Match: {match['match_type']} = {match['match_value']}")
                print(f"      Plan: {match['subscription_plan']}")
                print(f"      Vessel: {match['subscription_vessel']}")
                print()

        # Display no matches
        print(f"\n{'='*120}")
        print(f"\nNO MATCHES FOUND FOR {len(no_match)} CUSTOMERS:")
        print("="*120)
        no_match.sort(key=lambda x: x['invoice_mrr'], reverse=True)
        total_unmatched_mrr = 0
        for item in no_match:
            total_unmatched_mrr += item['invoice_mrr']
            vessels_str = ', '.join(item['invoice_vessels']) if item['invoice_vessels'] else 'No vessel'
            call_signs_str = ', '.join(item['invoice_call_signs']) if item['invoice_call_signs'] else 'No call sign'
            print(f"  {item['invoice_customer']:<50} {item['invoice_mrr']:>12,.2f} NOK | {call_signs_str:<15} | {vessels_str}")

        # Summary
        print(f"\n{'='*120}")
        print("SUMMARY")
        print("="*120)
        print(f"Customers with invoices but no subscriptions: {len(invoice_customers)}")
        print(f"  - Potential name mismatches: {len(matches_found)} ({total_matched_mrr:,.2f} NOK)")
        print(f"  - No vessel/call sign match: {len(no_match)} ({total_unmatched_mrr:,.2f} NOK)")
        print(f"\nIf all name mismatches are confirmed:")
        print(f"  Remaining unexplained gap from this category: {total_unmatched_mrr:,.2f} NOK")


if __name__ == "__main__":
    asyncio.run(check_name_mismatches())
