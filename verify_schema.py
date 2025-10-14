"""Verify Railway schema has all required columns"""
import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def verify():
    async with AsyncSessionLocal() as session:
        print("="*60)
        print("VERIFYING RAILWAY SCHEMA")
        print("="*60)

        # Check invoice_line_items columns
        result = await session.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'invoice_line_items'
            ORDER BY column_name;
        """))
        columns = result.fetchall()

        print("\ninvoice_line_items columns:")
        has_vessel = False
        has_call_sign = False
        for col_name, col_type in columns:
            if col_name == 'vessel_name':
                has_vessel = True
                print(f"  [OK] {col_name}: {col_type}")
            elif col_name == 'call_sign':
                has_call_sign = True
                print(f"  [OK] {col_name}: {col_type}")

        if not has_vessel:
            print("  [MISSING] vessel_name")
        if not has_call_sign:
            print("  [MISSING] call_sign")

        # Check invoice_mrr_snapshots columns
        result = await session.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'invoice_mrr_snapshots'
            ORDER BY column_name;
        """))
        columns = result.fetchall()

        print("\ninvoice_mrr_snapshots columns:")
        has_active_lines = False
        has_invoice_lines = False
        has_creditnote_lines = False
        for col_name, col_type in columns:
            if col_name == 'active_lines':
                has_active_lines = True
                print(f"  [OK] {col_name}: {col_type}")
            elif col_name == 'invoice_lines':
                has_invoice_lines = True
                print(f"  [OK] {col_name}: {col_type}")
            elif col_name == 'creditnote_lines':
                has_creditnote_lines = True
                print(f"  [OK] {col_name}: {col_type}")

        if not has_active_lines:
            print("  [MISSING] active_lines")
        if not has_invoice_lines:
            print("  [MISSING] invoice_lines")
        if not has_creditnote_lines:
            print("  [MISSING] creditnote_lines")

        print("\n" + "="*60)
        if has_vessel and has_call_sign and has_active_lines and has_invoice_lines and has_creditnote_lines:
            print("STATUS: ALL COLUMNS EXIST!")
        else:
            print("STATUS: SOME COLUMNS MISSING")
        print("="*60)

asyncio.run(verify())
