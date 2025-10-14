"""Check what period dates exist in Railway PostgreSQL"""
import asyncio
import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:fmjvxOqkfPbPDxegQwAaxkkgiigmEceO@shuttle.proxy.rlwy.net:36131/railway'

from sqlalchemy import text
from database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        print("="*80)
        print("CHECKING PERIOD DATES IN RAILWAY")
        print("="*80)

        # Check period date distribution
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total_lines,
                COUNT(period_start_date) as lines_with_start_date,
                COUNT(period_end_date) as lines_with_end_date,
                COUNT(CASE WHEN period_start_date IS NOT NULL AND period_end_date IS NOT NULL THEN 1 END) as lines_with_both_dates
            FROM invoice_line_items
        """))
        stats = result.first()

        print(f"\nLine Item Period Date Stats:")
        print(f"  Total line items: {stats[0]}")
        print(f"  Lines with start_date: {stats[1]}")
        print(f"  Lines with end_date: {stats[2]}")
        print(f"  Lines with both dates: {stats[3]}")

        # Check date ranges
        result = await session.execute(text("""
            SELECT
                MIN(period_start_date) as earliest_start,
                MAX(period_end_date) as latest_end
            FROM invoice_line_items
            WHERE period_start_date IS NOT NULL AND period_end_date IS NOT NULL
        """))
        date_range = result.first()

        print(f"\nDate Range:")
        print(f"  Earliest start: {date_range[0]}")
        print(f"  Latest end: {date_range[1]}")

        # Check for October 2025
        result = await session.execute(text("""
            SELECT COUNT(*) as count
            FROM invoice_line_items
            WHERE period_start_date <= '2025-10-01'
              AND period_end_date >= '2025-10-01'
        """))
        oct_2025_count = result.scalar()

        print(f"\nLine items active in October 2025: {oct_2025_count}")

        # Show sample of October 2025 line items
        if oct_2025_count > 0:
            result = await session.execute(text("""
                SELECT
                    ili.name,
                    ili.period_start_date,
                    ili.period_end_date,
                    ili.mrr_per_month,
                    i.customer_name
                FROM invoice_line_items ili
                JOIN invoices i ON ili.invoice_id = i.id
                WHERE ili.period_start_date <= '2025-10-01'
                  AND ili.period_end_date >= '2025-10-01'
                ORDER BY ili.mrr_per_month DESC
                LIMIT 10
            """))
            samples = result.fetchall()

            print(f"\nSample line items for October 2025:")
            for name, start, end, mrr, customer in samples:
                print(f"  - {customer}: {name}")
                print(f"    Period: {start} to {end}")
                print(f"    MRR: {mrr}")
        else:
            print("\nNo line items found for October 2025!")

            # Show what dates DO exist
            result = await session.execute(text("""
                SELECT
                    DATE_TRUNC('month', period_start_date) as month,
                    COUNT(*) as count
                FROM invoice_line_items
                WHERE period_start_date IS NOT NULL
                GROUP BY DATE_TRUNC('month', period_start_date)
                ORDER BY month DESC
                LIMIT 10
            """))
            months = result.fetchall()

            print("\nMost recent months with line items:")
            for month, count in months:
                print(f"  - {month}: {count} lines")

        print("\n" + "="*80)

asyncio.run(check())
