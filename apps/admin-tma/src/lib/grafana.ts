export const getGrafanaBaseUrl = () => {
  // Keep Grafana on a stable server domain (not ngrok). Can be overridden in env.
  const env = process.env.NEXT_PUBLIC_GRAFANA_BASE_URL;
  return (env && env.trim()) || "https://api.giftyai.ru/grafana";
};

export const openExternalLink = (url: string) => {
  try {
    // Prefer Telegram mini app API when available.
    const tg = (window as any)?.Telegram?.WebApp;
    if (tg?.openLink) {
      tg.openLink(url);
      return;
    }
  } catch {
    // ignore
  }
  window.open(url, "_blank", "noopener,noreferrer");
};

export const openGrafanaHome = () => openExternalLink(`${getGrafanaBaseUrl()}/`);

// MVP deep links.
// If Grafana Explore link format changes, these still land the user on Explore.
export const openGrafanaExploreLoki = (logql?: string) => {
  const base = getGrafanaBaseUrl();
  if (!logql) {
    openExternalLink(`${base}/explore`);
    return;
  }
  const left = encodeURIComponent(JSON.stringify({ datasource: "Loki", queries: [{ refId: "A", expr: logql }], range: { from: "now-15m", to: "now" } }));
  openExternalLink(`${base}/explore?left=${left}`);
};

export const openGrafanaExplorePrometheus = (promql?: string) => {
  const base = getGrafanaBaseUrl();
  if (!promql) {
    openExternalLink(`${base}/explore`);
    return;
  }
  const left = encodeURIComponent(JSON.stringify({ datasource: "Prometheus", queries: [{ refId: "A", expr: promql }], range: { from: "now-15m", to: "now" } }));
  openExternalLink(`${base}/explore?left=${left}`);
};

