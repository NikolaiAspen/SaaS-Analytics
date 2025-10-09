"""
Script to manually update expires_at for non_renewing subscriptions
based on scheduled_cancellation_date from Zoho API
"""
import asyncio
import json
from datetime import datetime
from dateutil import parser as date_parser
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.subscription import Subscription


async def main():
    # Load non_renewing data from the dump file
    with open("non_renewing_output.txt", "r", encoding="utf-8") as f:
        content = f.read()

    # Parse JSON objects from the file
    updates = {}  # subscription_id -> expires_date

    # Split by the separator lines
    sections = content.split("=" * 80)

    for section in sections:
        if '"subscription_id"' in section:
            try:
                # Find the JSON object
                json_start = section.find("{")
                if json_start >= 0:
                    json_str = section[json_start:]
                    data = json.loads(json_str)

                    sub_id = data.get("subscription_id")
                    scd = data.get("scheduled_cancellation_date")
                    customer = data.get("customer_name")

                    if sub_id and scd and scd not in ["", "None"]:
                        parsed_date = date_parser.parse(scd)
                        updates[sub_id] = (customer, parsed_date)
                        print(f"{customer} ({sub_id}): {parsed_date}")
            except Exception as e:
                pass

    print(f"\n\nFound {len(updates)} non_renewing subscriptions with dates")

    # Update database
    engine = create_async_engine('sqlite+aiosqlite:///data/app.db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        updated_count = 0

        for sub_id, (customer_name, expires_date) in updates.items():
            subscription = await session.get(Subscription, sub_id)

            if subscription:
                subscription.expires_at = expires_date
                updated_count += 1
                print(f"  [OK] Updated {sub_id} -> {expires_date}")
            else:
                print(f"  [SKIP] Not found in DB: {sub_id}")

        await session.commit()

    print(f"\n[SUCCESS] Updated {updated_count} subscriptions")


if __name__ == "__main__":
    asyncio.run(main())
