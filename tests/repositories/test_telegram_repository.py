
import pytest
from app.repositories.telegram import TelegramRepository
from app.models import TelegramSubscriber

@pytest.mark.asyncio
async def test_create_and_get_subscriber(postgres_session):
    repo = TelegramRepository(postgres_session)
    
    # Create
    chat_id = 123456
    sub = await repo.create_subscriber(chat_id, name="Test User", slug="testuser")
    assert sub.id is not None
    assert sub.chat_id == chat_id
    assert sub.name == "Test User"
    
    # Get by ID
    fetched = await repo.get_subscriber(chat_id)
    assert fetched is not None
    assert fetched.slug == "testuser"
    
    # Get by Slug
    fetched_slug = await repo.get_subscriber_by_slug("testuser")
    assert fetched_slug is not None
    assert fetched_slug.id == sub.id

@pytest.mark.asyncio
async def test_subscription_management(postgres_session):
    repo = TelegramRepository(postgres_session)
    
    chat_id = 999
    await repo.create_subscriber(chat_id, name="Subber")
    
    # Subscribe
    assert await repo.subscribe_topic(chat_id, "tech") is True
    sub = await repo.get_subscriber(chat_id)
    assert "tech" in sub.subscriptions
    
    # Subscribe duplicate (should be idempotent)
    assert await repo.subscribe_topic(chat_id, "tech") is True
    sub = await repo.get_subscriber(chat_id)
    assert sub.subscriptions.count("tech") == 1
    
    # Unsubscribe
    assert await repo.unsubscribe_topic(chat_id, "tech") is True
    sub = await repo.get_subscriber(chat_id)
    assert "tech" not in sub.subscriptions
    
    # Unsubscribe non-existent
    assert await repo.unsubscribe_topic(chat_id, "tech") is True

@pytest.mark.asyncio
async def test_get_subscribers_for_topic(postgres_session):
    repo = TelegramRepository(postgres_session)
    
    # Setup users
    s1 = await repo.create_subscriber(101, name="User1")
    s2 = await repo.create_subscriber(102, name="User2")
    s3 = await repo.create_subscriber(103, name="User3")
    
    await repo.subscribe_topic(101, "news")
    await repo.subscribe_topic(102, "news")
    await repo.subscribe_topic(103, "sport")
    
    # Test specific topic
    subs = await repo.get_subscribers_for_topic("news")
    assert len(subs) == 2
    ids = {s.chat_id for s in subs}
    assert 101 in ids
    assert 102 in ids
    
    # Test "all" topic logic if implemented (repo code implies it)
    await repo.subscribe_topic(103, "all")
    subs_news_or_all = await repo.get_subscribers_for_topic("news")
    # If logic is OR, then 103 should be included because it has "all"
    # The repo code: TelegramSubscriber.subscriptions.contains([topic]) OR TelegramSubscriber.subscriptions.contains(["all"])
    assert len(subs_news_or_all) == 3

@pytest.mark.asyncio
async def test_invite_system(postgres_session):
    repo = TelegramRepository(postgres_session)
    
    slug = "secret_invite"
    pw_hash = "hashed_secret"
    
    # Create Invite
    invite = await repo.create_invite(slug, "Invited One", pw_hash)
    assert invite.chat_id is None
    assert invite.invite_password_hash == pw_hash
    
    # Claim Invite (wrong hash)
    claimed = await repo.claim_invite(slug, "wrong_hash", 555)
    assert claimed is None
    
    # Claim Invite (correct)
    claimed = await repo.claim_invite(slug, pw_hash, 555)
    assert claimed is not None
    assert claimed.chat_id == 555
    assert claimed.invite_password_hash is None # Should be cleared
    assert claimed.name == "Invited One"

@pytest.mark.asyncio
async def test_permissions_and_roles(postgres_session):
    repo = TelegramRepository(postgres_session)
    chat_id = 777
    await repo.create_subscriber(chat_id)
    
    # Set Role
    assert await repo.set_role(chat_id, "admin") is True
    sub = await repo.get_subscriber(chat_id)
    assert sub.role == "admin"
    
    # Set Permissions
    perms = ["read", "write"]
    assert await repo.set_permissions(chat_id, perms) is True
    sub = await repo.get_subscriber(chat_id)
    assert sub.permissions == perms
