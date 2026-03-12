package contract

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"testing"

	"github.com/santhosh-tekuri/jsonschema/v5"
)

type snapshotItem struct {
	Channel string          `json:"channel"`
	Seq     uint64          `json:"seq"`
	Data    json.RawMessage `json:"data"`
}

type snapshotResp struct {
	Items []snapshotItem `json:"items"`
}

func TestAdminWSSnapshotContracts(t *testing.T) {
	base := os.Getenv("ADMIN_WS_CONTRACT_URL")
	if base == "" {
		t.Skip("ADMIN_WS_CONTRACT_URL not set")
	}
	indexPath := filepath.Join("..", "..", "..", "..", "contracts", "admin-ws", "index.json")
	indexBytes, err := os.ReadFile(indexPath)
	if err != nil {
		t.Fatalf("read index: %v", err)
	}
	var index struct {
		Channels []string `json:"channels"`
	}
	if err := json.Unmarshal(indexBytes, &index); err != nil {
		t.Fatalf("parse index: %v", err)
	}
	if len(index.Channels) == 0 {
		t.Fatal("no channels in index")
	}

	req, _ := http.NewRequest(http.MethodGet, base+"/api/v1/live-analytics/snapshot", nil)
	q := req.URL.Query()
	q.Set("channels", join(index.Channels))
	req.URL.RawQuery = q.Encode()
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("snapshot request: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		t.Fatalf("snapshot status: %d", resp.StatusCode)
	}
	var snap snapshotResp
	if err := json.NewDecoder(resp.Body).Decode(&snap); err != nil {
		t.Fatalf("decode snapshot: %v", err)
	}
	schemaCache := map[string]*jsonschema.Schema{}

	for _, item := range snap.Items {
		if item.Channel == "" {
			t.Fatal("snapshot item missing channel")
		}
		schemaPath := filepath.Join("..", "..", "..", "..", "contracts", "admin-ws", item.Channel+".json")
		schema, ok := schemaCache[schemaPath]
		if !ok {
			compiler := jsonschema.NewCompiler()
			if err := compiler.AddResource(schemaPath, mustRead(schemaPath)); err != nil {
				t.Fatalf("add schema %s: %v", schemaPath, err)
			}
			var err error
			schema, err = compiler.Compile(schemaPath)
			if err != nil {
				t.Fatalf("compile schema %s: %v", schemaPath, err)
			}
			schemaCache[schemaPath] = schema
		}
		var data interface{}
		if len(item.Data) == 0 {
			data = nil
		} else if err := json.Unmarshal(item.Data, &data); err != nil {
			t.Fatalf("decode data for %s: %v", item.Channel, err)
		}
		if err := schema.Validate(data); err != nil {
			t.Fatalf("schema validate %s: %v", item.Channel, err)
		}
	}
}

func mustRead(path string) *bytes.Reader {
	b, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	return bytes.NewReader(b)
}

func join(vals []string) string {
	if len(vals) == 0 {
		return ""
	}
	out := vals[0]
	for _, v := range vals[1:] {
		out += "," + v
	}
	return out
}
