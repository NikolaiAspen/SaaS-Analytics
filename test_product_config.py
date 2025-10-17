"""
Test script to verify product config service shows correct MRR status
"""
import asyncio
from database import AsyncSessionLocal
from services.product_config import ProductConfigService

async def test_products():
    async with AsyncSessionLocal() as session:
        service = ProductConfigService(session)
        products = await service.get_all_products()

        print("\n" + "="*100)
        print("TESTING PRODUCT CONFIGURATION SERVICE")
        print("="*100)
        print(f"\n{'Product Name':<50} {'Category':<20} {'MRR?':<10} Total MRR")
        print("-"*100)

        # Show first 20 products
        for product in products[:20]:
            product_name = product['product_name'][:48]

            # Get category (manual or auto)
            if product.get('config') and product['config'].get('category'):
                category = product['config']['category']
            elif product.get('auto_category'):
                category = product['auto_category'] + " (auto)"
            else:
                category = "-"

            # Get MRR status (manual or auto)
            is_recurring = product.get('auto_is_recurring', False)
            mrr_str = "YES" if is_recurring else "NO"

            total_mrr = product.get('total_mrr', 0.0)

            print(f"{product_name:<50} {category:<20} {mrr_str:<10} {total_mrr:>12,.0f} kr")

        print("="*100)

        # Count MRR vs non-MRR products
        mrr_count = sum(1 for p in products if p.get('auto_is_recurring'))
        non_mrr_count = len(products) - mrr_count

        print(f"\nTotal products: {len(products)}")
        print(f"MRR products (recurring): {mrr_count}")
        print(f"Non-MRR products: {non_mrr_count}")

        # Show breakdown
        mrr_total = sum(p.get('total_mrr', 0) for p in products if p.get('auto_is_recurring'))
        non_mrr_total = sum(p.get('total_mrr', 0) for p in products if not p.get('auto_is_recurring'))

        print(f"\nTotal MRR from recurring products: {mrr_total:,.0f} kr")
        print(f"Total from non-recurring products: {non_mrr_total:,.0f} kr")

if __name__ == "__main__":
    asyncio.run(test_products())
