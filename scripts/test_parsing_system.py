import httpx
import json
import time

BASE_URL = "http://localhost:8000/api/v1/internal"
TOKEN = "default_internal_token"
HEADERS = {"X-Internal-Token": TOKEN}

def test_parsing_flow():
    print("--- 1. Listing Sources ---")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{BASE_URL}/sources", headers=HEADERS)
            resp.raise_for_status()
            sources = resp.json()
            print(f"Found {len(sources)} sources")
            
            if not sources:
                print("No sources found. Creating a test source...")
                source_data = {
                    "site_key": "mrgeek",
                    "url": "https://mrgeek.ru/category/podarki/",
                    "type": "hub",
                    "strategy": "discovery",
                    "is_active": True
                }
                resp = client.post(f"{BASE_URL}/sources", json=source_data, headers=HEADERS)
                resp.raise_for_status()
                source = resp.json()
                print(f"Created source: {source['id']}")
            else:
                source = sources[0]
                
            source_id = source['id']
            print(f"Using source ID: {source_id} ({source['site_key']})")
            
            print("\n--- 2. Forcing Run ---")
            resp = client.post(f"{BASE_URL}/sources/{source_id}/force-run", headers=HEADERS)
            resp.raise_for_status()
            print(f"Force run response: {resp.json()}")
            
            print("\n--- 3. Simulating Ingestion (ingest-batch) ---")
            test_batch = {
                "items": [
                    {
                        "gift_id": f"{source['site_key']}:test_product_1",
                        "title": "Test Gift Product",
                        "price": 999.0,
                        "product_url": "https://example.com/item1",
                        "image_url": "https://example.com/img1.jpg",
                        "category": "Test Category",
                        "merchant": source['site_key'],
                        "content_text": "This is a test product content"
                    }
                ],
                "categories": [
                    {
                        "name": "New Discoverd Category",
                        "url": "https://example.com/cat1",
                        "site_key": source['site_key']
                    }
                ],
                "source_id": source_id,
                "stats": {"count": 1}
            }
            
            resp = client.post(f"{BASE_URL}/ingest-batch", json=test_batch, headers=HEADERS)
            resp.raise_for_status()
            print(f"Ingestion response: {resp.json()}")
            
            print("\n--- 4. Checking Monitoring ---")
            resp = client.get(f"{BASE_URL}/monitoring", headers=HEADERS)
            resp.raise_for_status()
            print(f"Monitoring stats: {resp.json()}")
            
            print("\n--- 5. Checking Category Mapping Tasks ---")
            resp = client.get(f"{BASE_URL}/categories/tasks", headers=HEADERS)
            resp.raise_for_status()
            tasks = resp.json()
            print(f"Found {len(tasks)} category mapping tasks")
            for t in tasks[:3]:
                 print(f" - {t['external_name']}")

    except Exception as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'response'):
            print(f"Response body: {e.response.text}")

if __name__ == "__main__":
    test_parsing_flow()
