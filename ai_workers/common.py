import requests
import logging

class GiftyInternalClient:
    def __init__(self, api_base, token):
        self.api_base = api_base.rstrip("/")
        self.headers = {"X-Internal-Token": token}
        self.logger = logging.getLogger("GiftyWorker")

    def get_scoring_tasks(self, limit=50):
        url = f"{self.api_base}/internal/scoring/tasks?limit={limit}"
        try:
            resp = requests.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Error fetching scoring tasks: {e}")
            return []

    def submit_scoring(self, results):
        url = f"{self.api_base}/internal/scoring/submit"
        try:
            resp = requests.post(url, json={"results": results}, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Error submitting scoring: {e}")
            return None

    def get_category_tasks(self, limit=100):
        url = f"{self.api_base}/internal/categories/tasks?limit={limit}"
        try:
            resp = requests.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Error fetching category tasks: {e}")
            return []

    def submit_categories(self, results):
        url = f"{self.api_base}/internal/categories/submit"
        try:
            resp = requests.post(url, json={"results": results}, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Error submitting categories: {e}")
            return None
