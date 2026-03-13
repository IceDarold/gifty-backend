from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

from clickhouse_driver import Client
from sqlalchemy import select, func

from app.config import get_settings
from app.db import get_session_context
from app.models import DiscoveredCategory, FrontendAllowedHost, FrontendApp, FrontendAuditLog, FrontendProfile, FrontendRelease, FrontendRule, FrontendRuntimeState, LLMLog, OpsRuntimeState, ParsingRun, ParsingSource, Product, TelegramSubscriber

logger = logging.getLogger("pg_ch_bootstrap")


def _ch_client() -> Client:
    settings = get_settings()
    host = 'clickhouse'
    port = 9000
    user = 'analytics'
    password = 'analytics'
    database = 'default'
    dsn = getattr(settings, 'clickhouse_dsn', '') or ''
    if 'clickhouse://' in dsn:
        no_scheme = dsn.split('://',1)[1]
        creds_host = no_scheme.split('/',1)[0]
        if '@' in creds_host:
            creds, hostport = creds_host.split('@',1)
            host = hostport.split(':',1)[0] or host
            if ':' in hostport:
                port = int(hostport.split(':',1)[1])
            if ':' in creds:
                user, password = creds.split(':',1)
        else:
            host = creds_host.split(':',1)[0] or host
    return Client(host=host, port=port, user=user, password=password, database=database)


def _upsert_sync_state(client: Client, sync_name: str):
    now = datetime.now(timezone.utc)
    client.execute(
        'INSERT INTO sync_state (sync_name, last_bootstrap_at, last_bootstrap_version, last_event_applied_at, last_event_id, lag_seconds) VALUES',
        [(sync_name, now, int(now.timestamp()), now, '', 0.0)]
    )


async def run_bootstrap() -> None:
    client = _ch_client()
    llm_days = int(os.getenv("LLM_BOOTSTRAP_DAYS", "30") or "30")
    llm_limit = int(os.getenv("LLM_BOOTSTRAP_LIMIT", "20000") or "20000")
    async with get_session_context() as session:
        sources = list((await session.execute(select(ParsingSource).order_by(ParsingSource.id.asc()))).scalars().all())
        discovery_items = list((await session.execute(select(DiscoveredCategory).order_by(DiscoveredCategory.id.desc()).limit(1000))).scalars().all())
        ops_runs = list((await session.execute(select(ParsingRun).order_by(ParsingRun.id.desc()).limit(1000))).scalars().all())
        products = list((await session.execute(select(Product).order_by(Product.product_id.asc()).limit(2000))).scalars().all())
        product_counts = list((await session.execute(
            select(Product.site_key, func.count()).group_by(Product.site_key)
        )).all())
        subscribers = list((await session.execute(select(TelegramSubscriber).order_by(TelegramSubscriber.id.asc()))).scalars().all())
        apps = list((await session.execute(select(FrontendApp).order_by(FrontendApp.id.asc()))).scalars().all())
        releases = list((await session.execute(select(FrontendRelease).order_by(FrontendRelease.id.asc()))).scalars().all())
        profiles = list((await session.execute(select(FrontendProfile).order_by(FrontendProfile.id.asc()))).scalars().all())
        rules = list((await session.execute(select(FrontendRule).order_by(FrontendRule.id.asc()))).scalars().all())
        allowed_hosts = list((await session.execute(select(FrontendAllowedHost).order_by(FrontendAllowedHost.id.asc()))).scalars().all())
        audit_logs = list((await session.execute(select(FrontendAuditLog).order_by(FrontendAuditLog.id.desc()).limit(500))).scalars().all())
        runtime_state = (await session.execute(select(FrontendRuntimeState).where(FrontendRuntimeState.id == 1))).scalar_one_or_none()
        ops_state = (await session.execute(select(OpsRuntimeState).where(OpsRuntimeState.id == 1))).scalar_one_or_none()
        llm_since = datetime.now(timezone.utc) - timedelta(days=llm_days)
        llm_logs = list((
            await session.execute(
                select(LLMLog)
                .where(LLMLog.created_at >= llm_since)
                .order_by(LLMLog.created_at.desc())
                .limit(llm_limit)
            )
        ).scalars().all())

    now = datetime.now(timezone.utc)
    def j(obj):
        import json
        return json.dumps(obj, default=str)

    client.execute('TRUNCATE TABLE IF EXISTS sources_latest')
    if sources:
        client.execute('INSERT INTO sources_latest (source_id, site_key, payload_json, version, deleted) VALUES', [
            (int(s.id), str(s.site_key or ''), j({
                'id': s.id, 'site_key': s.site_key, 'url': s.url, 'status': s.status, 'is_active': s.is_active, 'type': s.type, 'strategy': s.strategy, 'priority': s.priority, 'refresh_interval_hours': s.refresh_interval_hours, 'last_synced_at': s.last_synced_at, 'next_sync_at': s.next_sync_at, 'category_id': s.category_id, 'config': s.config, 'updated_at': getattr(s, 'updated_at', now), 'created_at': getattr(s, 'created_at', now),
            }), int(now.timestamp()), 0) for s in sources
        ])

    client.execute('TRUNCATE TABLE IF EXISTS subscribers_latest')
    if subscribers:
        client.execute('INSERT INTO subscribers_latest (subscriber_id, chat_id, payload_json, version, deleted) VALUES', [
            (int(s.id), int(s.chat_id or 0), j({'id': s.id, 'chat_id': s.chat_id, 'name': s.name, 'slug': s.slug, 'role': s.role, 'language': s.language, 'subscriptions': s.subscriptions, 'permissions': s.permissions, 'is_active': s.is_active, 'updated_at': getattr(s, 'updated_at', now), 'created_at': getattr(s, 'created_at', now)}), int(now.timestamp()), 0) for s in subscribers
        ])

    client.execute('TRUNCATE TABLE IF EXISTS frontend_apps_latest')
    if apps:
        client.execute('INSERT INTO frontend_apps_latest (app_id, app_key, payload_json, version, deleted) VALUES', [
            (int(a.id), str(a.key), j({'id': a.id, 'key': a.key, 'name': a.name, 'is_active': a.is_active, 'updated_at': getattr(a, 'updated_at', now), 'created_at': getattr(a, 'created_at', now)}), int(now.timestamp()), 0) for a in apps
        ])

    client.execute('TRUNCATE TABLE IF EXISTS frontend_releases_latest')
    if releases:
        client.execute('INSERT INTO frontend_releases_latest (release_id, app_id, payload_json, version, deleted) VALUES', [
            (int(r.id), int(r.app_id), j({'id': r.id, 'app_id': r.app_id, 'version': r.version, 'target_url': r.target_url, 'status': r.status, 'health_status': r.health_status, 'flags': r.flags, 'updated_at': getattr(r, 'updated_at', now), 'created_at': getattr(r, 'created_at', now)}), int(now.timestamp()), 0) for r in releases
        ])

    client.execute('TRUNCATE TABLE IF EXISTS frontend_profiles_latest')
    if profiles:
        client.execute('INSERT INTO frontend_profiles_latest (profile_id, profile_key, payload_json, version, deleted) VALUES', [
            (int(pr.id), str(pr.key), j({'id': pr.id, 'key': pr.key, 'name': pr.name, 'is_active': pr.is_active, 'updated_at': getattr(pr, 'updated_at', now), 'created_at': getattr(pr, 'created_at', now)}), int(now.timestamp()), 0) for pr in profiles
        ])

    client.execute('TRUNCATE TABLE IF EXISTS frontend_rules_latest')
    if rules:
        client.execute('INSERT INTO frontend_rules_latest (rule_id, profile_id, payload_json, version, deleted) VALUES', [
            (int(r.id), int(r.profile_id), j({'id': r.id, 'profile_id': r.profile_id, 'priority': r.priority, 'host_pattern': r.host_pattern, 'path_pattern': r.path_pattern, 'query_conditions': r.query_conditions, 'target_release_id': r.target_release_id, 'flags_override': r.flags_override, 'is_active': r.is_active, 'updated_at': getattr(r, 'updated_at', now), 'created_at': getattr(r, 'created_at', now)}), int(now.timestamp()), 0) for r in rules
        ])

    client.execute('TRUNCATE TABLE IF EXISTS frontend_allowed_hosts_latest')
    if allowed_hosts:
        client.execute('INSERT INTO frontend_allowed_hosts_latest (host_id, host, payload_json, version, deleted) VALUES', [
            (int(h.id), str(h.host), j({'id': h.id, 'host': h.host, 'is_active': h.is_active, 'updated_at': getattr(h, 'updated_at', now), 'created_at': getattr(h, 'created_at', now)}), int(now.timestamp()), 0) for h in allowed_hosts
        ])

    client.execute('TRUNCATE TABLE IF EXISTS frontend_audit_log_latest')
    if audit_logs:
        client.execute('INSERT INTO frontend_audit_log_latest (log_id, payload_json, version, deleted) VALUES', [
            (int(a.id), j({'id': a.id, 'actor_id': a.actor_id, 'action': a.action, 'entity_type': a.entity_type, 'entity_id': a.entity_id, 'before': a.before, 'after': a.after, 'created_at': getattr(a, 'created_at', now)}), int(now.timestamp()), 0) for a in audit_logs
        ])

    client.execute('TRUNCATE TABLE IF EXISTS ops_discovery_latest')
    if discovery_items:
        client.execute('INSERT INTO ops_discovery_latest (discovery_id, site_key, payload_json, version, deleted) VALUES', [
            (int(d.id), str(d.site_key), j({'id': d.id, 'hub_id': d.hub_id, 'site_key': d.site_key, 'url': d.url, 'name': d.name, 'parent_url': d.parent_url, 'state': d.state, 'promoted_source_id': d.promoted_source_id, 'meta': d.meta, 'created_at': getattr(d, 'created_at', now), 'updated_at': getattr(d, 'updated_at', now)}), int(now.timestamp()), 0) for d in discovery_items
        ])

    client.execute('TRUNCATE TABLE IF EXISTS categories_latest')
    if discovery_items:
        client.execute('INSERT INTO categories_latest (category_id, site_key, name, payload_json, version, deleted) VALUES', [
            (int(d.id), str(d.site_key), str(d.name or ''), j({'id': d.id, 'hub_id': d.hub_id, 'site_key': d.site_key, 'url': d.url, 'name': d.name, 'parent_url': d.parent_url, 'state': d.state, 'promoted_source_id': d.promoted_source_id, 'meta': d.meta, 'created_at': getattr(d, 'created_at', now), 'updated_at': getattr(d, 'updated_at', now)}), int(now.timestamp()), 0) for d in discovery_items
        ])

    client.execute('TRUNCATE TABLE IF EXISTS ops_runs_latest')
    if ops_runs:
        client.execute('INSERT INTO ops_runs_latest (run_id, source_id, payload_json, version, deleted) VALUES', [
            (int(r.id), int(r.source_id), j({'id': r.id, 'source_id': r.source_id, 'status': r.status, 'items_scraped': r.items_scraped, 'items_new': r.items_new, 'error_message': r.error_message, 'duration_seconds': r.duration_seconds, 'logs': r.logs, 'created_at': getattr(r, 'created_at', now), 'updated_at': getattr(r, 'updated_at', now)}), int(now.timestamp()), 0) for r in ops_runs
        ])

    client.execute('TRUNCATE TABLE IF EXISTS products_latest')
    if products:
        client.execute('INSERT INTO products_latest (product_id, merchant, category, title, payload_json, version, deleted) VALUES', [
            (str(p.product_id), str(p.merchant or ''), str(p.category or ''), str(p.title or ''), j({'product_id': p.product_id, 'title': p.title, 'description': p.description, 'price': float(p.price) if p.price is not None else None, 'currency': p.currency, 'image_url': p.image_url, 'product_url': p.product_url, 'merchant': p.merchant, 'category': p.category, 'raw': p.raw, 'is_active': p.is_active, 'content_text': p.content_text, 'content_hash': p.content_hash, 'site_key': p.site_key, 'created_at': getattr(p, 'created_at', now), 'updated_at': getattr(p, 'updated_at', now)}), int(now.timestamp()), 0) for p in products
        ])
    client.execute('TRUNCATE TABLE IF EXISTS products_count_by_site')
    if product_counts:
        client.execute('INSERT INTO products_count_by_site (site_key, cnt, updated_at) VALUES', [
            (str(site_key or ''), int(cnt), now) for site_key, cnt in product_counts if site_key
        ])

    client.execute('TRUNCATE TABLE IF EXISTS settings_runtime_latest')
    if runtime_state is not None:
        client.execute('INSERT INTO settings_runtime_latest (setting_key, payload_json, version, deleted) VALUES', [('frontend_runtime_state', j({'id': runtime_state.id, 'active_profile_id': runtime_state.active_profile_id, 'fallback_release_id': runtime_state.fallback_release_id, 'sticky_enabled': runtime_state.sticky_enabled, 'sticky_ttl_seconds': runtime_state.sticky_ttl_seconds, 'cache_ttl_seconds': runtime_state.cache_ttl_seconds, 'updated_by': runtime_state.updated_by, 'updated_at': runtime_state.updated_at}), int(now.timestamp()), 0)])
    if ops_state is not None:
        client.execute('INSERT INTO settings_runtime_latest (setting_key, payload_json, version, deleted) VALUES', [('ops_runtime_state', j({'id': ops_state.id, 'scheduler_paused': ops_state.scheduler_paused, 'settings_version': ops_state.settings_version, 'ops_aggregator_enabled': ops_state.ops_aggregator_enabled, 'ops_aggregator_interval_ms': ops_state.ops_aggregator_interval_ms, 'ops_snapshot_ttl_ms': ops_state.ops_snapshot_ttl_ms, 'ops_stale_max_age_ms': ops_state.ops_stale_max_age_ms, 'ops_client_intervals': ops_state.ops_client_intervals, 'updated_by': ops_state.updated_by, 'updated_at': ops_state.updated_at}), int(now.timestamp()), 0)])

    if llm_logs:
        llm_events = []
        llm_metrics = []
        for log in llm_logs:
            created_at = getattr(log, 'created_at', now) or now
            event_id = f"llm.log:{log.id}"
            payload = {
                'id': str(log.id),
                'provider': log.provider,
                'model': log.model,
                'call_type': log.call_type,
                'status': log.status,
                'error_type': log.error_type,
                'error_message': log.error_message,
                'prompt_tokens': log.prompt_tokens,
                'completion_tokens': log.completion_tokens,
                'total_tokens': log.total_tokens,
                'latency_ms': log.latency_ms,
                'provider_latency_ms': log.provider_latency_ms,
                'queue_latency_ms': log.queue_latency_ms,
                'postprocess_latency_ms': log.postprocess_latency_ms,
                'cost_usd': float(log.cost_usd) if log.cost_usd is not None else None,
                'provider_request_id': log.provider_request_id,
                'prompt_hash': log.prompt_hash,
                'session_id': log.session_id,
                'experiment_id': log.experiment_id,
                'variant_id': log.variant_id,
                'finish_reason': log.finish_reason,
                'params': log.params,
                'system_prompt': log.system_prompt,
                'output_content': log.output_content,
                'created_at': created_at,
                'usage_captured': True,
                'provider_request_captured': True,
            }
            llm_events.append((
                event_id,
                created_at,
                'llm.log',
                '',
                '',
                '',
                j({
                    'provider': log.provider,
                    'model': log.model,
                    'call_type': log.call_type,
                    'status': log.status,
                }),
                j(payload),
                0.0,
                int(created_at.timestamp()),
            ))

            metric_event_id = f"llm.call_completed:{log.id}"
            dims = j({
                'provider': log.provider,
                'model': log.model,
                'call_type': log.call_type,
                'status': log.status,
            })
            llm_metrics.extend([
                (
                    metric_event_id,
                    created_at,
                    'llm.call_completed',
                    'llm.call_completed',
                    '',
                    '',
                    dims,
                    '',
                    1.0,
                    int(created_at.timestamp()),
                ),
                (
                    metric_event_id,
                    created_at,
                    'llm.call_completed',
                    'llm.call_completed.total_tokens',
                    '',
                    '',
                    dims,
                    '',
                    float(log.total_tokens or 0),
                    int(created_at.timestamp()),
                ),
                (
                    metric_event_id,
                    created_at,
                    'llm.call_completed',
                    'llm.call_completed.latency_ms',
                    '',
                    '',
                    dims,
                    '',
                    float(log.latency_ms or 0),
                    int(created_at.timestamp()),
                ),
                (
                    metric_event_id,
                    created_at,
                    'llm.call_completed',
                    'llm.call_completed.cost_usd',
                    '',
                    '',
                    dims,
                    '',
                    float(log.cost_usd or 0),
                    int(created_at.timestamp()),
                ),
            ])
        if llm_events:
            client.execute(
                'INSERT INTO analytics_events (event_id, occurred_at, event_type, metric, scope, scope_key, dims_json, payload_json, value, version) VALUES',
                llm_events,
            )
        if llm_metrics:
            client.execute(
                'INSERT INTO analytics_events (event_id, occurred_at, event_type, metric, scope, scope_key, dims_json, payload_json, value, version) VALUES',
                llm_metrics,
            )

    _upsert_sync_state(client, 'pg-ch-bootstrap')
    logger.info('Bootstrap sync completed')


if __name__ == '__main__':
    asyncio.run(run_bootstrap())
