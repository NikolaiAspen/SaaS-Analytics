"""Quick check of September 2025 invoice MRR"""
import asyncio
from database import AsyncSessionLocal
from services.invoice import InvoiceService

async def check():
    async with AsyncSessionLocal() as session:
        service = InvoiceService(session)
        mrr = await service.get_mrr_for_month('2025-09')
        print(f'September 2025 Invoice MRR: {mrr:,.2f} NOK')

asyncio.run(check())
