"""Check if current month snapshot exists in Railway"""
import asyncio
from database import AsyncSessionLocal
from datetime import datetime
from sqlalchemy import select
from models.invoice import InvoiceMRRSnapshot, Invoice, InvoiceLineItem

async def check():
    async with AsyncSessionLocal() as session:
        current_month = datetime.utcnow().strftime("%Y-%m")

        # Check if snapshot exists for current month
        stmt = select(InvoiceMRRSnapshot).where(InvoiceMRRSnapshot.month == current_month)
        result = await session.execute(stmt)
        snapshot = result.scalar_one_or_none()

        print("="*60)
        print(f"CURRENT MONTH CHECK: {current_month}")
        print("="*60)

        if snapshot:
            print(f"Snapshot EXISTS for {current_month}")
            print(f"  MRR: {snapshot.mrr:,.2f} NOK")
            print(f"  ARR: {snapshot.arr:,.2f} NOK")
            print(f"  Customers: {snapshot.total_customers}")
            print(f"  Active invoices: {snapshot.active_invoices}")
        else:
            print(f"NO SNAPSHOT for {current_month}")

            # Count invoices for current month
            from services.invoice import InvoiceService
            invoice_service = InvoiceService(session)

            mrr = await invoice_service.get_mrr_for_month(current_month)
            print(f"\nCalculated MRR for {current_month}: {mrr:,.2f} NOK")

            # Count total invoices
            stmt = select(Invoice).where(Invoice.invoice_date >= datetime(2025, 10, 1))
            result = await session.execute(stmt)
            invoices = result.scalars().all()
            print(f"Invoices in October 2025: {len(invoices)}")

        print("="*60)

asyncio.run(check())
