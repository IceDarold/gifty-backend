package dedup

import (
	"testing"
	"time"
)

func TestDedupCache(t *testing.T) {
	c := New(10 * time.Second)
	now := time.Now().UTC()
	if c.IsDuplicate("a", now) {
		t.Fatal("first event must not be duplicate")
	}
	if !c.IsDuplicate("a", now.Add(time.Second)) {
		t.Fatal("same id in ttl must be duplicate")
	}
	if c.IsDuplicate("a", now.Add(11*time.Second)) {
		t.Fatal("after ttl must not be duplicate")
	}
}
