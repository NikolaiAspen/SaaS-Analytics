"""
Test script to check Zoho API invoice structure
"""

import asyncio
import httpx
import json
from config import settings
from services.zoho import ZohoClient


async def test_invoice_structure():
    """Fetch one invoice and print its structure"""

    # Initialize Zoho client
    zoho_client = ZohoClient(
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        refresh_token=settings.zoho_refresh_token,
        org_id=settings.zoho_org_id,
        base_url=settings.zoho_base,
    )

    # First get list of invoices
    url = f"{zoho_client.base_url}/billing/v1/invoices"
    headers = await zoho_client._get_headers()

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get first invoice ID
        response = await client.get(url, headers=headers, params={"per_page": 1})
        response.raise_for_status()
        data = response.json()

        invoices = data.get('invoices', [])
        if not invoices:
            print("No invoices found!")
            return

        invoice_id = invoices[0].get('invoice_id')
        print(f"Testing with invoice ID: {invoice_id}")
        print(f"Invoice number: {invoices[0].get('invoice_number')}")

        # Fetch detailed invoice
        detail_url = f"{zoho_client.base_url}/billing/v1/invoices/{invoice_id}"
        detail_response = await client.get(detail_url, headers=headers)
        detail_response.raise_for_status()
        detail_data = detail_response.json()

        print("\n" + "="*80)
        print("FULL API RESPONSE:")
        print("="*80)
        print(json.dumps(detail_data, indent=2))

        print("\n" + "="*80)
        print("CHECKING LINE ITEMS:")
        print("="*80)

        # Try to find line items
        invoice_data = detail_data.get('invoice')
        if invoice_data:
            print("Found 'invoice' key")
            print(f"Keys in invoice: {list(invoice_data.keys())}")

            # Check for line_items
            line_items = invoice_data.get('line_items', [])
            print(f"\nLine items count: {len(line_items)}")

            if line_items:
                print("\nFirst line item:")
                print(json.dumps(line_items[0], indent=2))
            else:
                print("\nNo line_items found!")
                print("Looking for alternative keys...")
                for key in invoice_data.keys():
                    if 'item' in key.lower() or 'line' in key.lower():
                        print(f"  Found key: {key}")
                        print(f"  Value: {invoice_data[key]}")


if __name__ == "__main__":
    asyncio.run(test_invoice_structure())
