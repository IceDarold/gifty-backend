import { execSync } from "node:child_process";
import type { APIRequestContext } from "@playwright/test";

export type IntegrationEnv = {
  appBaseUrl: string;
  apiBaseUrl: string;
  liveBaseUrl: string;
  dockerNetwork: string;
  internalToken: string;
  liveWsToken: string;
  natsPublishEnabled: boolean;
};

export function getIntegrationEnv(): IntegrationEnv {
  return {
    appBaseUrl: process.env.E2E_APP_BASE_URL || "http://127.0.0.1:3001",
    apiBaseUrl: process.env.E2E_API_BASE_URL || "http://127.0.0.1:8000",
    liveBaseUrl: process.env.E2E_LIVE_ANALYTICS_BASE_URL || "http://127.0.0.1:8095",
    dockerNetwork: process.env.E2E_DOCKER_NETWORK || "gifty-backend_default",
    internalToken: process.env.E2E_INTERNAL_API_TOKEN || process.env.NEXT_PUBLIC_API_INTERNAL_TOKEN || "",
    liveWsToken: process.env.E2E_LIVE_ANALYTICS_WS_TOKEN || process.env.NEXT_PUBLIC_LIVE_ANALYTICS_WS_TOKEN || "dev-live-analytics-token",
    natsPublishEnabled: process.env.E2E_PUBLISH_NATS_EVENT !== "0",
  };
}

export async function precheckIntegration(request: APIRequestContext, env: IntegrationEnv) {
  const checks = [
    `${env.appBaseUrl}/`,
    `${env.apiBaseUrl}/docs`,
    `${env.liveBaseUrl}/health`,
  ];

  for (const url of checks) {
    try {
      const resp = await request.get(url, { timeout: 8000 });
      if (!resp.ok()) return { ok: false, reason: `precheck failed: ${url} -> ${resp.status()}` };
    } catch (e) {
      return { ok: false, reason: `precheck failed: ${url} -> ${(e as Error).message}` };
    }
  }

  try {
    const authResp = await request.get(`${env.apiBaseUrl}/api/v1/internal/ops/runtime-settings`, {
      timeout: 8000,
      headers: env.internalToken ? { "x-internal-token": env.internalToken } : undefined,
    });
    if (!authResp.ok()) {
      return { ok: false, reason: `precheck failed: internal auth -> ${authResp.status()}` };
    }
  } catch (e) {
    return { ok: false, reason: `precheck failed: internal auth -> ${(e as Error).message}` };
  }

  return { ok: true, reason: "ok" };
}

export function publishNatsEvent(env: IntegrationEnv, options?: { eventId?: string; count?: number }): { ok: boolean; details: string } {
  const eventId = options?.eventId || `e2e-${Date.now()}`;
  const count = options?.count ?? 1;
  const payload = {
    event_id: eventId,
    event_type: "kpi.quiz_started",
    version: 1,
    occurred_at: new Date().toISOString(),
    source: "internal",
    tenant_id: "e2e",
    dims: {
      scope: "global",
      scope_key: "kpi",
    },
    metrics: {
      count,
      sum: count,
      min: 1,
      max: count,
    },
    payload: {
      note: "e2e publish",
    },
  };

  const cmd = [
    "docker run --rm",
    `--network ${env.dockerNetwork}`,
    "natsio/nats-box:latest",
    "nats pub",
    "-s nats://nats:4222",
    "analytics.events.v1.kpi.quiz_started",
    `'${JSON.stringify(payload)}'`,
  ].join(" ");

  try {
    const out = execSync(cmd, { stdio: ["ignore", "pipe", "pipe"] }).toString();
    return { ok: true, details: out.trim() || "published" };
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return { ok: false, details: message };
  }
}

export async function publishEventsAndWaitForUI(
  request: APIRequestContext,
  env: IntegrationEnv,
  opts?: { expectedDelta?: number; timeoutMs?: number; attempts?: number },
): Promise<{ ok: boolean; details: string }> {
  const timeoutMs = opts?.timeoutMs ?? 12000;
  const expectedDelta = opts?.expectedDelta ?? 1;
  const attempts = opts?.attempts ?? 1;

  const snapshotUrl = `${env.liveBaseUrl}/api/v1/live-analytics/snapshot?channels=global.kpi`;
  const attemptLogs: string[] = [];

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const beforeResp = await request.get(snapshotUrl);
    const beforeJson = (await beforeResp.json()) as { items?: Array<{ data?: { count?: number } }> };
    const beforeCount = beforeJson?.items?.[0]?.data?.count ?? 0;

    const eventId = `e2e-${Date.now()}-${attempt}`;
    const published = publishNatsEvent(env, { eventId, count: expectedDelta });
    if (!published.ok) return { ok: false, details: published.details };

    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      const afterResp = await request.get(snapshotUrl);
      if (!afterResp.ok()) continue;
      const afterJson = (await afterResp.json()) as { items?: Array<{ data?: { count?: number } }> };
      const afterCount = afterJson?.items?.[0]?.data?.count ?? 0;
      if (afterCount >= beforeCount + expectedDelta) {
        return { ok: true, details: `attempt ${attempt}: count ${beforeCount} -> ${afterCount}` };
      }
    }
    attemptLogs.push(`attempt ${attempt} timed out (count ${beforeCount} +${expectedDelta})`);
  }

  return { ok: false, details: `snapshot did not advance within ${timeoutMs}ms; ${attemptLogs.join("; ")}` };
}
