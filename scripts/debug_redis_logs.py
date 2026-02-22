import redis
import os
import sys

def listen(source_id):
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Connecting to Redis at {url}...")
    r = redis.from_url(url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"logs:source:{source_id}"
    pubsub.subscribe(channel)
    print(f"Subscribed to {channel}. Waiting for messages...")
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            print(f"Received: {message['data']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 debug_redis_logs.py <source_id>")
        sys.exit(1)
    listen(sys.argv[1])
