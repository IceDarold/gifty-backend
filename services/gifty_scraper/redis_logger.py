import redis
import os
import json
import logging
from datetime import datetime

class RedisLogHandler(logging.Handler):
    def __init__(self, redis_url=None, source_id=None):
        super().__init__()
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.source_id = source_id
        self.channel = f"logs:source:{source_id}" if source_id else None
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        except Exception as e:
            print(f"Failed to connect to Redis for logging: {e}")
            self.redis_client = None

    def emit(self, record):
        if not self.redis_client or not self.channel:
            return
            
        try:
            log_entry = self.format(record)
            # Publish for live listeners
            self.redis_client.publish(self.channel, log_entry)
            
            # Also store in a buffer for new connections
            buffer_key = f"{self.channel}:buffer"
            pipe = self.redis_client.pipeline()
            pipe.rpush(buffer_key, log_entry)
            pipe.ltrim(buffer_key, -100, -1) # Keep last 100
            pipe.expire(buffer_key, 3600) # Expire after 1 hour if no activity
            pipe.execute()
            
            # Internal trace (will go to subprocess stdout)
            # print(f"DEBUG_REDIS: Published to {self.channel}", flush=True)
        except Exception:
            pass

def setup_redis_logging(spider):
    source_id = getattr(spider, 'source_id', None)
    if not source_id:
        print(f"DEBUG_REDIS: No source_id for spider {spider.name}")
        return
        
    print(f"DEBUG_REDIS: Initializing Redis logging for source {source_id}")
    handler = RedisLogHandler(source_id=source_id)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
    
    # Add handler to the spider's logger and the 'scrapy' logger
    spider.logger.logger.addHandler(handler)
    logging.getLogger('scrapy').addHandler(handler)
    
    print(f"DEBUG_REDIS: Handler added to spider and 'scrapy' loggers")
    return handler
