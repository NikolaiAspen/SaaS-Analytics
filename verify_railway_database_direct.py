"""
Connect DIRECTLY to Railway PostgreSQL and show exact data for invoice 2010783
"""
import asyncio
import asyncpg

async def verify_railway_data():
    """Connect directly to Railway database using asyncpg"""

    # Railway PostgreSQL connection
    DATABASE_URL = "postgresql://postgres:fmjvxOqkfPbPDxegQwAaxkkgiigmEceO@shuttle.proxy.rlwy.net:36131/railway"

    print("=" * 80)
    print("CONNECTING DIRECTLY TO RAILWAY POSTGRESQL")
    print(f"URL: {DATABASE_URL[:60]}...")
    print("=" * 80)

    # Connect directly with asyncpg (no SQLAlchemy)
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get invoice
        invoice = await conn.fetchrow("""
            SELECT id, invoice_number, customer_name, invoice_date, transaction_type
            FROM invoices
            WHERE invoice_number = '2010783'
        """)

        if not invoice:
            print("\n[ERROR] Invoice 2010783 not found!")
            return

        print(f"\nInvoice found:")
        print(f"  ID: {invoice['id']}")
        print(f"  Number: {invoice['invoice_number']}")
        print(f"  Customer: {invoice['customer_name']}")
        print(f"  Date: {invoice['invoice_date']}")
        print(f"  Type: {invoice['transaction_type']}")

        # Get line items - RAW DATA directly from database
        line_items = await conn.fetch("""
            SELECT
                id,
                name,
                description,
                period_start_date,
                period_end_date,
                period_months,
                item_total,
                mrr_per_month,
                vessel_name,
                call_sign
            FROM invoice_line_items
            WHERE invoice_id = $1
            ORDER BY id
        """, invoice['id'])

        print(f"\n{'='*80}")
        print(f"LINE ITEMS FROM RAILWAY DATABASE ({len(line_items)} items):")
        print(f"{'='*80}")

        for idx, item in enumerate(line_items, 1):
            print(f"\n--- LINE ITEM {idx} ---")
            print(f"  ID: {item['id']}")
            print(f"  Product: {item['name']}")
            print(f"  Period: {item['period_start_date']} to {item['period_end_date']}")
            print(f"  Period months: {item['period_months']}")
            print(f"  Item total: {item['item_total']} kr")
            print(f"  MRR per month: {item['mrr_per_month']} kr")
            print(f"  Vessel: {item['vessel_name']}")
            print(f"  Call sign: {item['call_sign']}")

        # Now check credit note
        print(f"\n{'='*80}")
        print("CHECKING CREDIT NOTE CN-02032")
        print(f"{'='*80}")

        cn_invoice = await conn.fetchrow("""
            SELECT id, invoice_number, customer_name, invoice_date, transaction_type
            FROM invoices
            WHERE invoice_number = 'CN-02032'
        """)

        if cn_invoice:
            print(f"\nCredit Note found:")
            print(f"  ID: {cn_invoice['id']}")
            print(f"  Number: {cn_invoice['invoice_number']}")

            cn_items = await conn.fetch("""
                SELECT
                    id,
                    name,
                    period_start_date,
                    period_end_date,
                    period_months,
                    item_total,
                    mrr_per_month
                FROM invoice_line_items
                WHERE invoice_id = $1
            """, cn_invoice['id'])

            print(f"\nCredit Note line items: {len(cn_items)}")
            for item in cn_items:
                print(f"  Product: {item['name']}")
                print(f"  Period: {item['period_start_date']} to {item['period_end_date']}")
                print(f"  MRR: {item['mrr_per_month']} kr")

        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Invoice 2010783 MRR: {line_items[0]['mrr_per_month']} kr")
        if cn_items:
            print(f"Credit Note CN-02032 MRR: {cn_items[0]['mrr_per_month']} kr")
            print(f"Net MRR: {line_items[0]['mrr_per_month'] + cn_items[0]['mrr_per_month']} kr")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_railway_data())
