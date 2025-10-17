"""
Create Product Configuration Table

This script creates the product_configurations table in the database.
"""

import asyncio
from database import init_db

async def main():
    print("\n" + "="*80)
    print("CREATING PRODUCT CONFIGURATION TABLE")
    print("="*80 + "\n")

    print("[1/1] Creating tables...")
    await init_db()

    print("\n✅ Product configuration table created successfully!")
    print("\nTable: product_configurations")
    print("Columns:")
    print("  - product_name (PRIMARY KEY)")
    print("  - category")
    print("  - period_months")
    print("  - is_recurring")
    print("  - notes")
    print("  - created_at")
    print("  - updated_at")
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
