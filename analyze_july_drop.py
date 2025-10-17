"""
Analyze the significant MRR drop from July to August 2025
"""

import asyncio
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from database import AsyncSessionLocal
from models.accounting import AccountingReceivableItem
from services.accounting import AccountingService

async def analyze_july_drop():
    async with AsyncSessionLocal() as session:
        service = AccountingService(session)

        # Calculate end of July and August
        july_end = datetime(2025, 7, 31, 23, 59, 59)
        august_end = datetime(2025, 8, 31, 23, 59, 59)

        # Get items active in July
        stmt_july = select(AccountingReceivableItem).where(
            AccountingReceivableItem.period_start_date <= july_end,
            AccountingReceivableItem.period_end_date >= july_end
        )
        result = await session.execute(stmt_july)
        july_items = result.scalars().all()

        # Get items active in August
        stmt_august = select(AccountingReceivableItem).where(
            AccountingReceivableItem.period_start_date <= august_end,
            AccountingReceivableItem.period_end_date >= august_end
        )
        result = await session.execute(stmt_august)
        august_items = result.scalars().all()

        # Categorize items
        july_mrr_items = []
        august_mrr_items = []

        for item in july_items:
            category = service.categorize_item(item.item_name)
            if service.is_recurring_category(category) and item.mrr_per_month:
                july_mrr_items.append({
                    'item': item,
                    'category': category,
                    'mrr': item.mrr_per_month
                })

        for item in august_items:
            category = service.categorize_item(item.item_name)
            if service.is_recurring_category(category) and item.mrr_per_month:
                august_mrr_items.append({
                    'item': item,
                    'category': category,
                    'mrr': item.mrr_per_month
                })

        # Find items that were in July but not in August
        july_ids = {item['item'].id for item in july_mrr_items}
        august_ids = {item['item'].id for item in august_mrr_items}

        disappeared_ids = july_ids - august_ids
        new_ids = august_ids - july_ids

        print("\n" + "="*80)
        print("ANALYSE: MRR NEDGANG FRA JULI TIL AUGUST 2025")
        print("="*80)

        # Calculate totals
        july_total = sum(item['mrr'] for item in july_mrr_items)
        august_total = sum(item['mrr'] for item in august_mrr_items)

        print(f"\nJuli MRR: {july_total:,.2f} kr")
        print(f"August MRR: {august_total:,.2f} kr")
        print(f"Differanse: {august_total - july_total:,.2f} kr ({((august_total - july_total) / july_total * 100):.2f}%)")

        # Items that disappeared
        print(f"\n\n{'='*80}")
        print(f"ITEMS SOM FORSVANT (var i juli, ikke i august): {len(disappeared_ids)}")
        print(f"{'='*80}\n")

        disappeared_items = [item for item in july_mrr_items if item['item'].id in disappeared_ids]
        disappeared_items.sort(key=lambda x: abs(x['mrr']), reverse=True)

        total_disappeared = sum(item['mrr'] for item in disappeared_items)
        print(f"Total MRR som forsvant: {total_disappeared:,.2f} kr\n")

        # Group by customer
        by_customer = {}
        for item in disappeared_items:
            customer = item['item'].customer_name
            if customer not in by_customer:
                by_customer[customer] = []
            by_customer[customer].append(item)

        # Sort customers by total MRR impact
        sorted_customers = sorted(by_customer.items(), key=lambda x: sum(i['mrr'] for i in x[1]), reverse=True)

        print("TOP 20 KUNDER MED ITEMS SOM FORSVANT:\n")
        for i, (customer, items) in enumerate(sorted_customers[:20], 1):
            customer_mrr = sum(item['mrr'] for item in items)
            print(f"{i}. {customer}: {customer_mrr:,.2f} kr ({len(items)} items)")
            for item in items[:5]:  # Show max 5 items per customer
                print(f"   - {item['item'].item_name}: {item['mrr']:,.2f} kr")
                print(f"     Periode: {item['item'].period_start_date.strftime('%d.%m.%Y')} - {item['item'].period_end_date.strftime('%d.%m.%Y')}")
                print(f"     Transaction: {item['item'].transaction_number} ({item['item'].transaction_type})")
            if len(items) > 5:
                print(f"   ... og {len(items) - 5} flere items")
            print()

        # New items in August
        print(f"\n{'='*80}")
        print(f"NYE ITEMS (ikke i juli, men i august): {len(new_ids)}")
        print(f"{'='*80}\n")

        new_items = [item for item in august_mrr_items if item['item'].id in new_ids]
        new_items.sort(key=lambda x: abs(x['mrr']), reverse=True)

        total_new = sum(item['mrr'] for item in new_items)
        print(f"Total ny MRR: {total_new:,.2f} kr\n")

        print("TOP 10 NYE ITEMS:\n")
        for i, item in enumerate(new_items[:10], 1):
            print(f"{i}. {item['item'].customer_name}: {item['mrr']:,.2f} kr")
            print(f"   {item['item'].item_name}")
            print(f"   Periode: {item['item'].period_start_date.strftime('%d.%m.%Y')} - {item['item'].period_end_date.strftime('%d.%m.%Y')}")
            print()

        # Category breakdown
        print(f"\n{'='*80}")
        print("KATEGORIER SOM FORSVANT")
        print(f"{'='*80}\n")

        by_category = {}
        for item in disappeared_items:
            cat = item['category']
            if cat not in by_category:
                by_category[cat] = 0
            by_category[cat] += item['mrr']

        for cat, mrr in sorted(by_category.items(), key=lambda x: abs(x[1]), reverse=True):
            print(f"{cat}: {mrr:,.2f} kr")

if __name__ == "__main__":
    asyncio.run(analyze_july_drop())
