"""
Test script to check product categorization
"""
import asyncio
from database import AsyncSessionLocal
from sqlalchemy import select, func
from models.accounting import AccountingReceivableItem
from services.accounting import AccountingService

async def test_categorization():
    async with AsyncSessionLocal() as session:
        # Get top 10 products by count
        query = select(
            AccountingReceivableItem.item_name,
            func.count(AccountingReceivableItem.item_id).label('count')
        ).group_by(AccountingReceivableItem.item_name).order_by(func.count(AccountingReceivableItem.item_id).desc()).limit(20)

        result = await session.execute(query)
        products = result.all()

        print("\n" + "="*100)
        print("TESTING PRODUCT CATEGORIZATION")
        print("="*100)
        print(f"\n{'Product Name':<50} {'Category':<20} {'Recurring?':<12} Count")
        print("-"*100)

        for row in products:
            product_name = row.item_name
            category = AccountingService.categorize_item(product_name)
            is_recurring = AccountingService.is_recurring_category(category)

            recurring_str = "YES (MRR)" if is_recurring else "NO"
            print(f"{product_name[:48]:<50} {category:<20} {recurring_str:<12} {row.count}")

        print("="*100)

if __name__ == "__main__":
    asyncio.run(test_categorization())
