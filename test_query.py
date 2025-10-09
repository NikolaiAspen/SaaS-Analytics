import asyncio
from datetime import datetime
from database import get_session
from services.metrics import MetricsCalculator

async def test():
    async for session in get_session():
        calc = MetricsCalculator(session)

        print(f"Current UTC time: {datetime.utcnow()}")
        print(f"Current local time: {datetime.now()}")
        print()

        # Test with debug=True
        mrr = await calc.calculate_mrr(debug=True)
        print(f"\nFinal MRR: {mrr}")

        # Get full metrics
        metrics = await calc.get_metrics_summary()
        print(f"\nMetrics summary:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")

        break

asyncio.run(test())
