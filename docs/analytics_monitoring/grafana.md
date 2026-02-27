# Grafana Under `/grafana`

This project uses **Grafana OSS** for observability UI (Loki logs, Prometheus metrics, and later Tempo traces).

## Goal

Expose Grafana behind nginx at:

- `https://api.giftyai.ru/grafana/` (temporary)
- later: `https://analytics.giftyai.ru/grafana/`

## Docker Compose

`docker-compose.yml` includes a `grafana` service bound to localhost:

- `127.0.0.1:3000 -> grafana:3000`

Grafana is configured to serve from a subpath:

- `GF_SERVER_ROOT_URL=%(protocol)s://%(domain)s/grafana/`
- `GF_SERVER_SERVE_FROM_SUB_PATH=true`

Datasources are provisioned automatically:

- Prometheus: `http://prometheus:9090`
- Loki: `http://loki:3100`

## nginx (api.giftyai.ru)

Add this inside the `server { server_name api.giftyai.ru; ... }` block:

```nginx
# Grafana under /grafana/
location /grafana/ {
  # Important: no trailing slash here, otherwise nginx will strip `/grafana/`
  # and Grafana will get stuck in a redirect loop.
  proxy_pass http://127.0.0.1:3000;

  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;

  proxy_read_timeout 60s;
  proxy_send_timeout 60s;
}

# Grafana Live (websocket)
location /grafana/api/live/ {
  proxy_pass http://127.0.0.1:3000;

  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";

  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;

  proxy_read_timeout 60s;
}
```

Then validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Notes

- Grafana will redirect unauthenticated users to `/grafana/login`.
- For a fast MVP, keep Grafana login as-is. Later, protect via nginx basic auth / IP allowlist / SSO.
