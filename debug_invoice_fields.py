"""
Quick debug: Check what fields Zoho actually returns for invoice items
"""

import asyncio
import httpx
import json
from config import settings
from services.zoho import ZohoClient


async def check_invoice_fields():
    """Fetch one invoice and print ALL field names"""

    # Initialize Zoho client
    zoho_client = ZohoClient(
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        refresh_token=settings.zoho_refresh_token,
        org_id=settings.zoho_org_id,
        base_url=settings.zoho_base,
    )

    # Get first invoice ID
    url = f"{zoho_client.base_url}/billing/v1/invoices"
    headers = await zoho_client._get_headers()

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get first invoice
        response = await client.get(url, headers=headers, params={"per_page": 1})
        response.raise_for_status()
        data = response.json()

        invoices = data.get('invoices', [])
        if not invoices:
            print("No invoices found!")
            return

        invoice_id = invoices[0].get('invoice_id')
        print(f"Testing invoice ID: {invoice_id}")

        # Fetch detailed invoice
        detail_url = f"{zoho_client.base_url}/billing/v1/invoices/{invoice_id}"
        detail_response = await client.get(detail_url, headers=headers)
        detail_response.raise_for_status()
        detail_data = detail_response.json()

        # Print the response structure
        print("\n" + "="*80)
        print("KEYS IN API RESPONSE:")
        print("="*80)
        for key in detail_data.keys():
            print(f"  - {key}")

        # Check for invoice object
        if 'invoice' in detail_data:
            invoice_obj = detail_data['invoice']
            print("\n" + "="*80)
            print("KEYS IN 'invoice' OBJECT:")
            print("="*80)
            for key in invoice_obj.keys():
                print(f"  - {key}")

            # Check for line items
            print("\n" + "="*80)
            print("CHECKING LINE ITEM FIELDS:")
            print("="*80)

            # Try all possible field names
            possible_fields = [
                'invoice_items',
                'line_items',
                'items',
                'invoiceitems',
                'lineitems'
            ]

            for field in possible_fields:
                value = invoice_obj.get(field)
                if value is not None:
                    print(f"  FOUND '{field}': {len(value)} items")
                    if len(value) > 0:
                        print(f"\n    First item keys:")
                        for item_key in value[0].keys():
                            print(f"      - {item_key}")

                        print(f"\n    FULL FIRST ITEM:")
                        print(json.dumps(value[0], indent=2))
                else:
                    print(f"  '{field}': NOT FOUND")


if __name__ == "__main__":
    asyncio.run(check_invoice_fields())
