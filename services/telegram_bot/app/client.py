import httpx
import logging

class TelegramInternalClient:
    def __init__(self, api_base: str, token: str, analytics_token: str = None):
        self.api_base = api_base.rstrip("/")
        self.headers = {"X-Internal-Token": token}
        self.analytics_headers = {"X-Analytics-Token": analytics_token} if analytics_token else {}
        self.logger = logging.getLogger("TelegramBot")

    async def get_subscriber(self, chat_id: int):
        url = f"{self.api_base}/internal/telegram/subscribers/{chat_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
            return None

    async def create_subscriber(self, chat_id: int, name: str = None, slug: str = None):
        url = f"{self.api_base}/internal/telegram/subscribers"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, 
                json={"chat_id": chat_id, "name": name, "slug": slug}, 
                headers=self.headers
            )
            return resp.json() if resp.status_code == 200 else None

    async def subscribe(self, chat_id: int, topic: str):
        url = f"{self.api_base}/internal/telegram/subscribers/{chat_id}/subscribe"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params={"topic": topic}, headers=self.headers)
            return resp.status_code == 200

    async def unsubscribe(self, chat_id: int, topic: str):
        url = f"{self.api_base}/internal/telegram/subscribers/{chat_id}/unsubscribe"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params={"topic": topic}, headers=self.headers)
            return resp.status_code == 200

    async def get_topic_subscribers(self, topic: str):
        url = f"{self.api_base}/internal/telegram/topics/{topic}/subscribers"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
            return []

    async def get_stats(self):
        url = f"{self.api_base}/analytics/stats"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.analytics_headers)
            return resp.json() if resp.status_code == 200 else None

    async def get_technical_health(self):
        url = f"{self.api_base}/analytics/technical"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.analytics_headers)
            return resp.json() if resp.status_code == 200 else None

    async def get_scraping_monitoring(self):
        url = f"{self.api_base}/analytics/scraping"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.analytics_headers)
            return resp.json() if resp.status_code == 200 else None

    async def set_language(self, chat_id: int, language: str):
        url = f"{self.api_base}/internal/telegram/subscribers/{chat_id}/language"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params={"language": language}, headers=self.headers)
            return resp.status_code == 200

    async def get_trends(self, days: int = 7):
        url = f"{self.api_base}/analytics/trends"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"days": days}, headers=self.analytics_headers)
            return resp.json() if resp.status_code == 200 else None

    async def get_sources(self):
        url = f"{self.api_base}/internal/sources"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            return resp.json() if resp.status_code == 200 else []

    async def get_source_details(self, source_id: int):
        url = f"{self.api_base}/internal/sources/{source_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            return resp.json() if resp.status_code == 200 else None

    async def toggle_source(self, source_id: int, is_active: bool):
        url = f"{self.api_base}/internal/sources/{source_id}/toggle"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params={"is_active": is_active}, headers=self.headers)
            return resp.status_code == 200

    async def force_run_source(self, source_id: int, strategy: str = None):
        url = f"{self.api_base}/internal/sources/{source_id}/force-run"
        params = {"strategy": strategy} if strategy else {}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, headers=self.headers)
            return resp.status_code == 200

    async def update_source(self, source_id: int, data: dict):
        url = f"{self.api_base}/internal/sources/{source_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.patch(url, json=data, headers=self.headers)
            return resp.status_code == 200
