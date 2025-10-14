import httpx
from typing import List, Dict, Optional
from datetime import datetime


class ZohoClient:
    """Client for interacting with Zoho Billing API"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        org_id: str,
        base_url: str = "https://www.zohoapis.eu",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.org_id = org_id
        self.base_url = base_url.rstrip("/")
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def _refresh_access_token(self) -> str:
        """Refresh the OAuth2 access token using refresh token"""
        url = "https://accounts.zoho.eu/oauth/v2/token"
        params = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params)
            response.raise_for_status()
            data = response.json()

            self.access_token = data["access_token"]
            # Token typically expires in 3600 seconds
            return self.access_token

    async def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers with valid access token"""
        if not self.access_token:
            await self._refresh_access_token()

        return {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "X-com-zoho-subscriptions-organizationid": self.org_id,
        }

    async def get_subscriptions(
        self,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 200,
        last_modified_time: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch subscriptions from Zoho Billing

        Args:
            status: Filter by status (live, cancelled, expired, etc.)
            page: Page number for pagination
            per_page: Number of results per page (max 200)
            last_modified_time: Filter by last modified time (ISO format)

        Returns:
            List of subscription dictionaries
        """
        url = f"{self.base_url}/billing/v1/subscriptions"
        params = {"page": page, "per_page": per_page}

        # Note: Zoho API filter_by seems to cause 400 errors
        # We'll fetch all subscriptions and filter in memory instead
        # if status:
        #     params["filter_by"] = f"Status.{status}"

        if last_modified_time:
            params["last_modified_time"] = last_modified_time

        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                return data.get("subscriptions", [])
            except httpx.HTTPStatusError as e:
                print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                print(f"Error fetching subscriptions: {str(e)}")
                raise

    async def get_all_subscriptions(self, last_modified_time: Optional[str] = None, include_cancelled: bool = True) -> List[Dict]:
        """
        Fetch all subscriptions across all pages

        Args:
            last_modified_time: Filter by last modified time (ISO format) - NOTE: Cannot be used with status filter
            include_cancelled: If True, fetch all statuses including cancelled (default: True)

        Returns:
            List of all subscription dictionaries
        """
        all_subscriptions = []
        page = 1
        per_page = 200

        # Zoho API filter_by causes 400 errors, so we fetch ALL subscriptions
        # and filter in memory based on status
        print(f"Fetching all subscriptions from Zoho...")
        if last_modified_time:
            print(f"  (modified since {last_modified_time})")

        while True:
            subs = await self.get_subscriptions(
                status=None,  # Don't use filter_by - causes 400 error
                page=page,
                per_page=per_page,
                last_modified_time=last_modified_time
            )
            if not subs:
                break

            all_subscriptions.extend(subs)

            if len(subs) < per_page:
                break

            page += 1

        # Filter in memory if we don't want all subscriptions
        if not include_cancelled:
            # Only keep live and non_renewing
            all_subscriptions = [
                sub for sub in all_subscriptions
                if sub.get("status") in ["live", "non_renewing"]
            ]
            print(f"Filtered to {len(all_subscriptions)} live/non_renewing subscriptions")

        print(f"Total subscriptions fetched: {len(all_subscriptions)}")
        return all_subscriptions

    async def get_subscription(self, subscription_id: str) -> Dict:
        """
        Fetch a single subscription by ID

        Args:
            subscription_id: Zoho subscription ID

        Returns:
            Subscription dictionary
        """
        url = f"{self.base_url}/billing/v1/subscriptions/{subscription_id}"
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            return data.get("subscription", {})

    async def get_customers(self, page: int = 1, per_page: int = 200) -> List[Dict]:
        """
        Fetch customers from Zoho Billing

        Args:
            page: Page number for pagination
            per_page: Number of results per page (max 200)

        Returns:
            List of customer dictionaries
        """
        url = f"{self.base_url}/billing/v1/customers"
        params = {"page": page, "per_page": per_page}
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            return data.get("customers", [])

    async def get_creditnotes(
        self,
        page: int = 1,
        per_page: int = 200,
        last_modified_time: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch credit notes from Zoho Billing

        Args:
            page: Page number for pagination
            per_page: Number of results per page (max 200)
            last_modified_time: Filter by last modified time (ISO format)

        Returns:
            List of credit note dictionaries
        """
        url = f"{self.base_url}/billing/v1/creditnotes"
        params = {"page": page, "per_page": per_page}

        if last_modified_time:
            params["last_modified_time"] = last_modified_time

        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                return data.get("creditnotes", [])
            except httpx.HTTPStatusError as e:
                print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                print(f"Error fetching credit notes: {str(e)}")
                raise

    async def get_all_creditnotes(self, last_modified_time: Optional[str] = None) -> List[Dict]:
        """
        Fetch all credit notes across all pages

        Args:
            last_modified_time: Filter by last modified time (ISO format)

        Returns:
            List of all credit note dictionaries
        """
        all_creditnotes = []
        page = 1
        per_page = 200

        print(f"Fetching all credit notes from Zoho...")
        if last_modified_time:
            print(f"  (modified since {last_modified_time})")

        while True:
            creditnotes = await self.get_creditnotes(
                page=page,
                per_page=per_page,
                last_modified_time=last_modified_time
            )
            if not creditnotes:
                break

            all_creditnotes.extend(creditnotes)

            if len(creditnotes) < per_page:
                break

            page += 1

        print(f"Total credit notes fetched: {len(all_creditnotes)}")
        return all_creditnotes

    async def get_creditnote(self, creditnote_id: str) -> Dict:
        """
        Fetch a single credit note by ID with line items

        Args:
            creditnote_id: Zoho credit note ID

        Returns:
            Credit note dictionary with line items
        """
        url = f"{self.base_url}/billing/v1/creditnotes/{creditnote_id}"
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            return data.get("creditnote", {})
