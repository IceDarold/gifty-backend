from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.telegram import TelegramRepository


class _Res:
    def __init__(self, *, scalar=None, scalars_items=None):
        self._scalar = scalar
        self._scalars_items = scalars_items or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalars_items))


@pytest.mark.anyio
async def test_claim_invite_returns_none_when_not_found():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalar=None))
    repo = TelegramRepository(session)
    assert await repo.claim_invite("s", "h", 1) is None


@pytest.mark.anyio
async def test_claim_invite_sets_name_when_missing():
    session = AsyncMock()
    session.commit = AsyncMock()
    sub = SimpleNamespace(chat_id=None, invite_password_hash="h", name=None)
    session.execute = AsyncMock(return_value=_Res(scalar=sub))
    repo = TelegramRepository(session)
    out = await repo.claim_invite("s", "h", 777, name="X")
    assert out.chat_id == 777
    assert out.invite_password_hash is None
    assert out.name == "X"


@pytest.mark.anyio
async def test_subscribe_unsubscribe_return_false_when_missing_subscriber():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalar=None))
    repo = TelegramRepository(session)
    assert await repo.subscribe_topic(1, "t") is False
    assert await repo.unsubscribe_topic(1, "t") is False


@pytest.mark.anyio
async def test_get_subscribers_for_topic_sqlite_branch_filters_in_python():
    session = AsyncMock()
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    subs = [
        SimpleNamespace(is_active=True, subscriptions=["news"], chat_id=1),
        SimpleNamespace(is_active=True, subscriptions=["all"], chat_id=2),
        SimpleNamespace(is_active=True, subscriptions=["sports"], chat_id=3),
    ]
    session.execute = AsyncMock(return_value=_Res(scalars_items=subs))
    repo = TelegramRepository(session)
    out = await repo.get_subscribers_for_topic("news")
    ids = {s.chat_id for s in out}
    assert ids == {1, 2}


@pytest.mark.anyio
async def test_get_subscriber_by_id_calls_execute():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalar=SimpleNamespace(id=1)))
    repo = TelegramRepository(session)
    out = await repo.get_subscriber_by_id(1)
    assert out.id == 1


@pytest.mark.anyio
async def test_create_subscriber_and_invite_commit(monkeypatch):
    session = AsyncMock()
    session.add = lambda _obj: None
    session.commit = AsyncMock()
    repo = TelegramRepository(session)

    sub = await repo.create_subscriber(123, name="N", slug="s")
    assert sub.chat_id == 123
    assert sub.slug == "s"

    invite = await repo.create_invite("slug", "Name", "hash", mentor_id=1, permissions=["p"])
    assert invite.chat_id is None
    assert invite.permissions == ["p"]
    assert session.commit.await_count >= 2


@pytest.mark.anyio
async def test_subscribe_and_unsubscribe_update_lists_and_commit():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalar=SimpleNamespace(chat_id=1, subscriptions=[], permissions=[])))
    repo = TelegramRepository(session)

    assert await repo.subscribe_topic(1, "news") is True
    assert session.commit.await_count == 1

    # idempotent subscribe doesn't commit again
    assert await repo.subscribe_topic(1, "news") is True
    assert session.commit.await_count == 1

    assert await repo.unsubscribe_topic(1, "news") is True
    assert session.commit.await_count == 2

    # idempotent unsubscribe doesn't commit again
    assert await repo.unsubscribe_topic(1, "news") is True
    assert session.commit.await_count == 2


@pytest.mark.anyio
async def test_get_subscribers_for_topic_postgres_branch_executes_query():
    session = AsyncMock()
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    session.execute = AsyncMock(return_value=_Res(scalars_items=[SimpleNamespace(chat_id=1)]))
    repo = TelegramRepository(session)
    out = await repo.get_subscribers_for_topic("news")
    assert out[0].chat_id == 1


@pytest.mark.anyio
async def test_language_roles_permissions_and_list_all():
    session = AsyncMock()
    session.commit = AsyncMock()

    sub = SimpleNamespace(chat_id=1, language=None, role=None, permissions=[])
    session.execute = AsyncMock(
        side_effect=[
            _Res(scalar=sub),  # set_language get_subscriber
            _Res(scalar=sub),  # set_role get_subscriber
            _Res(scalar=sub),  # set_permissions get_subscriber
            _Res(scalars_items=[sub]),  # get_all_subscribers
        ]
    )
    repo = TelegramRepository(session)
    assert await repo.set_language(1, "ru") is True
    assert sub.language == "ru"
    assert await repo.set_role(1, "admin") is True
    assert sub.role == "admin"
    assert await repo.set_permissions(1, ["x"]) is True
    assert sub.permissions == ["x"]
    assert (await repo.get_all_subscribers())[0].chat_id == 1
