import aiohttp
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, cryptopanic_api_key: str, cryptopanic_api_url: str):
        self.cryptopanic_api_key = cryptopanic_api_key
        self.cryptopanic_api_url = cryptopanic_api_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_crypto_news(self) -> Dict[str, Any]:
        """Fetch crypto news from CryptoPanic API."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")

        try:
            async with self.session.get(
                self.cryptopanic_api_url,
                params={
                    "auth_token": self.cryptopanic_api_key,
                    "filter": "rising",
                    "public": "true"
                },
                timeout=10
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return {"results": []}