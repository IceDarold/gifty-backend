#!/usr/bin/env python3
"""
Script to fetch and display all events tracked in PostHog.
This helps us understand what data is available for analytics.
"""
import httpx
import os
from dotenv import load_dotenv
import json

load_dotenv()

POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY")
POSTHOG_PROJECT_ID = os.getenv("POSTHOG_PROJECT_ID")
POSTHOG_API_BASE = "https://app.posthog.com/api"


def fetch_event_definitions():
    """Fetch all event definitions from PostHog."""
    url = f"{POSTHOG_API_BASE}/projects/{POSTHOG_PROJECT_ID}/event_definitions/"
    headers = {"Authorization": f"Bearer {POSTHOG_API_KEY}"}
    
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def main():
    print("🦔 Fetching events from PostHog...\n")
    
    try:
        data = fetch_event_definitions()
        
        # PostHog returns paginated results
        events = data.get("results", [])
        
        if not events:
            print("❌ No events found. Make sure the frontend is sending events.")
            return
        
        print(f"✅ Found {len(events)} event types:\n")
        print("=" * 60)
        
        for event in events:
            name = event.get("name", "Unknown")
            volume = event.get("volume_30_day", 0)
            last_seen = event.get("last_seen_at", "Never")
            
            print(f"📊 {name}")
            print(f"   Volume (30d): {volume}")
            print(f"   Last seen: {last_seen}")
            print("-" * 60)
        
        # Save to file for reference
        with open("posthog_events.json", "w") as f:
            json.dump(events, f, indent=2)
        
        print("\n💾 Full data saved to: posthog_events.json")
        
    except httpx.HTTPStatusError as e:
        print(f"❌ API Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    main()
