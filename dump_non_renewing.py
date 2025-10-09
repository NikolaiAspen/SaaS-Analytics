import asyncio
import json
from services.zoho import ZohoClient
from config import settings

async def main():
    zoho = ZohoClient(
        settings.zoho_client_id,
        settings.zoho_client_secret,
        settings.zoho_refresh_token,
        settings.zoho_org_id
    )

    print("Fetching all subscriptions from Zoho...")
    all_subs = await zoho.get_all_subscriptions()

    print(f"Total subscriptions: {len(all_subs)}")

    non_renewing = [sub for sub in all_subs if sub.get("status") == "non_renewing"]

    print(f"Non-renewing subscriptions: {len(non_renewing)}")

    # Save to file
    with open("non_renewing_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Checking for NON_RENEWING output...\n")
        for sub in non_renewing:
            f.write(f"\n{'='*80}\n")
            f.write(f"Customer: {sub.get('customer_name')}\n")
            f.write(f"Status: {sub.get('status')}\n")
            f.write(f"scheduled_cancellation_date: {sub.get('scheduled_cancellation_date')}\n")
            f.write(f"expires_at: {sub.get('expires_at')}\n")
            f.write(f"current_term_ends_at: {sub.get('current_term_ends_at')}\n")
            f.write(f"next_billing_at: {sub.get('next_billing_at')}\n")
            f.write(f"{'='*80}\n")
            f.write(json.dumps(sub, indent=2, default=str))
            f.write("\n")

    print(f"Output saved to non_renewing_output.txt")

if __name__ == "__main__":
    asyncio.run(main())
