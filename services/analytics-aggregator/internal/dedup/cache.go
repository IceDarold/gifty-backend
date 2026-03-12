package dedup

import (
	"sync"
	"time"
)

type Cache struct {
	mu   sync.Mutex
	ttl  time.Duration
	seen map[string]time.Time
}

func New(ttl time.Duration) *Cache {
	return &Cache{ttl: ttl, seen: make(map[string]time.Time)}
}

func (c *Cache) IsDuplicate(id string, now time.Time) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	if ts, ok := c.seen[id]; ok {
		if now.Sub(ts) <= c.ttl {
			return true
		}
	}
	c.seen[id] = now
	return false
}

func (c *Cache) Cleanup(now time.Time) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for k, ts := range c.seen {
		if now.Sub(ts) > c.ttl {
			delete(c.seen, k)
		}
	}
}
