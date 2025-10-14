"""
Test gap analysis for September 2025 to see how it handles the specific customers
"""

import asyncio
from database import AsyncSessionLocal
from services.invoice import InvoiceService


async def test_gap():
    """Test gap analysis for September 2025"""

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)

        print("="*100)
        print("TESTING GAP ANALYSIS FOR SEPTEMBER 2025")
        print("="*100)

        result = await invoice_service.analyze_mrr_gap("2025-09")

        print(f"\nGap Overview:")
        print(f"  Total gap MRR (truly unmatched): {result['total_gap_mrr']:,.2f} kr")
        print(f"  Matched gap MRR (name mismatches but found via call sign/vessel): {result['matched_gap_mrr']:,.2f} kr")
        print(f"  Unmatched gap MRR: {result['unmatched_gap_mrr']:,.2f} kr")
        print(f"  Customers with name mismatch (but matched): {result['customers_with_name_mismatch']}")
        print(f"  Customers truly without subscriptions: {result['customers_truly_without_subs']}")
        print(f"  Customers without invoices: {result['customers_without_invoices']}")
        print(f"  Matched by call sign: {result['matched_by_call_sign']}")
        print(f"  Matched by vessel: {result['matched_by_vessel']}")
        print(f"  Unmatched: {result['unmatched_customers']}")

        print(f"\nTop 10 customers with NAME MISMATCH (but matched via call sign/vessel):")
        print("-"*100)
        for i, customer in enumerate(result['customers_with_name_mismatch_list'][:10], 1):
            print(f"\n{i}. {customer['customer_name']}: {customer['mrr']:,.2f} kr")
            print(f"   Vessels: {', '.join(customer['vessels'][:3])}")
            print(f"   Call signs: {', '.join(customer['call_signs'][:3])}")

            if customer['matches']:
                print(f"   MATCHES FOUND:")
                for match in customer['matches']:
                    print(f"     -> {match['subscription_customer']} (via {match['type']}: {match['value']})")

        print(f"\n\nTop 10 customers TRULY WITHOUT SUBSCRIPTIONS:")
        print("-"*100)
        for i, customer in enumerate(result['customers_truly_without_subs_list'][:10], 1):
            print(f"\n{i}. {customer['customer_name']}: {customer['mrr']:,.2f} kr")
            print(f"   Vessels: {', '.join(customer['vessels'][:3])}")
            print(f"   Call signs: {', '.join(customer['call_signs'][:3])}")

            if customer['matches']:
                print(f"   MATCHES FOUND:")
                for match in customer['matches']:
                    print(f"     -> {match['subscription_customer']} (via {match['type']}: {match['value']})")
            else:
                print(f"   NO MATCHES")


if __name__ == "__main__":
    asyncio.run(test_gap())
