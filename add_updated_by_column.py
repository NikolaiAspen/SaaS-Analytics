"""
Add updated_by column to product_configurations table in PostgreSQL
"""
import asyncio
from sqlalchemy import text
from database import engine

async def add_column():
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'product_configurations'
            );
        """))
        table_exists = result.scalar()

        if table_exists:
            print("[OK] Table 'product_configurations' exists")

            # Check if column exists
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = 'product_configurations'
                    AND column_name = 'updated_by'
                );
            """))
            column_exists = result.scalar()

            if column_exists:
                print("[OK] Column 'updated_by' already exists - no migration needed")
            else:
                print("Adding 'updated_by' column...")
                await conn.execute(text("""
                    ALTER TABLE product_configurations
                    ADD COLUMN updated_by VARCHAR(100) DEFAULT 'admin';
                """))
                print("[OK] Column 'updated_by' added successfully!")
        else:
            print("[OK] Table doesn't exist yet - it will be created with the new column when first config is saved")

if __name__ == "__main__":
    asyncio.run(add_column())
    print("\n[SUCCESS] Database migration complete!")
