from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_stream_source_logs_emits_connected_and_closes(fake_redis):
    from routes import internal as internal_routes

    resp = await internal_routes.stream_source_logs(source_id=123, redis=fake_redis)
    iterator = resp.body_iterator
    first = await iterator.__anext__()
    assert "[CONNECTED]" in first
    await iterator.aclose()


@pytest.mark.asyncio
async def test_get_source_log_stream_emits_connected_when_no_buffered_logs(fake_redis):
    from routes import internal as internal_routes

    resp = await internal_routes.get_source_log_stream(source_id=321, redis=fake_redis)
    iterator = resp.body_iterator
    first = await iterator.__anext__()
    assert "[CONNECTED]" in first
    await iterator.aclose()
