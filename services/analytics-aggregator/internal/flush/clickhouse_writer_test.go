package flush

import "testing"

func TestParseDSNDefaults(t *testing.T) {
	got := parseDSN("")
	if got.Addr != "clickhouse:9000" {
		t.Fatalf("addr: got %q", got.Addr)
	}
	if got.Database != "default" {
		t.Fatalf("database: got %q", got.Database)
	}
	if got.Username != "default" {
		t.Fatalf("username: got %q", got.Username)
	}
	if got.Password != "" {
		t.Fatalf("password: got %q", got.Password)
	}
}

func TestParseDSNWithAuthAndDB(t *testing.T) {
	got := parseDSN("clickhouse://analytics:analytics@clickhouse:9000/default")
	if got.Addr != "clickhouse:9000" {
		t.Fatalf("addr: got %q", got.Addr)
	}
	if got.Database != "default" {
		t.Fatalf("database: got %q", got.Database)
	}
	if got.Username != "analytics" {
		t.Fatalf("username: got %q", got.Username)
	}
	if got.Password != "analytics" {
		t.Fatalf("password: got %q", got.Password)
	}
}

func TestParseDSNHostOnly(t *testing.T) {
	got := parseDSN("clickhouse:9000")
	if got.Addr != "clickhouse:9000" {
		t.Fatalf("addr: got %q", got.Addr)
	}
	if got.Database != "default" {
		t.Fatalf("database: got %q", got.Database)
	}
	if got.Username != "default" {
		t.Fatalf("username: got %q", got.Username)
	}
}

