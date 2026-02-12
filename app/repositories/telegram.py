from __future__ import annotations
from typing import Optional, List, Sequence
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import TelegramSubscriber

class TelegramRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_subscriber(self, chat_id: int) -> Optional[TelegramSubscriber]:
        stmt = select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_subscriber_by_slug(self, slug: str) -> Optional[TelegramSubscriber]:
        stmt = select(TelegramSubscriber).where(TelegramSubscriber.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_subscriber_by_id(self, sub_id: int) -> Optional[TelegramSubscriber]:
        stmt = select(TelegramSubscriber).where(TelegramSubscriber.id == sub_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    async def create_subscriber(self, chat_id: int, name: Optional[str] = None, slug: Optional[str] = None) -> TelegramSubscriber:
        subscriber = TelegramSubscriber(
            chat_id=chat_id,
            name=name,
            slug=slug,
            subscriptions=[],
            permissions=[]
        )
        self.session.add(subscriber)
        await self.session.commit()
        return subscriber

    async def create_invite(
        self,
        slug: str,
        name: Optional[str],
        password_hash: str,
        mentor_id: Optional[int] = None,
        permissions: Optional[list[str]] = None,
    ) -> TelegramSubscriber:
        subscriber = TelegramSubscriber(
            chat_id=None,
            name=name,
            slug=slug,
            invite_password_hash=password_hash,
            mentor_id=mentor_id,
            subscriptions=[],
            permissions=permissions or [],
        )
        self.session.add(subscriber)
        await self.session.commit()
        return subscriber

    async def claim_invite(
        self,
        slug: str,
        password_hash: str,
        chat_id: int,
        name: Optional[str] = None,
    ) -> Optional[TelegramSubscriber]:
        stmt = select(TelegramSubscriber).where(
            and_(
                TelegramSubscriber.slug == slug,
                TelegramSubscriber.invite_password_hash == password_hash,
                TelegramSubscriber.chat_id.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        sub = result.scalar_one_or_none()
        if not sub:
            return None
        sub.chat_id = chat_id
        sub.invite_password_hash = None
        if name and not sub.name:
            sub.name = name
        await self.session.commit()
        return sub
    async def subscribe_topic(self, chat_id: int, topic: str) -> bool:
        sub = await self.get_subscriber(chat_id)
        if not sub:
            return False
        
        current_subs = list(sub.subscriptions)
        if topic not in current_subs:
            current_subs.append(topic)
            sub.subscriptions = current_subs
            await self.session.commit()
        return True

    async def unsubscribe_topic(self, chat_id: int, topic: str) -> bool:
        sub = await self.get_subscriber(chat_id)
        if not sub:
            return False
        
        current_subs = list(sub.subscriptions)
        if topic in current_subs:
            current_subs.remove(topic)
            sub.subscriptions = current_subs
            await self.session.commit()
        return True

    async def get_subscribers_for_topic(self, topic: str) -> Sequence[TelegramSubscriber]:
        # Using JSONB contains filter
        # @> '["topic"]'
        from sqlalchemy import or_
        stmt = select(TelegramSubscriber).where(
            and_(
                TelegramSubscriber.is_active == True,
                or_(
                    TelegramSubscriber.subscriptions.contains([topic]),
                    TelegramSubscriber.subscriptions.contains(["all"])
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_language(self, chat_id: int, language: str) -> bool:
        sub = await self.get_subscriber(chat_id)
        if not sub:
            return False
        sub.language = language
        await self.session.commit()
        return True

    async def get_all_subscribers(self) -> Sequence[TelegramSubscriber]:
        stmt = select(TelegramSubscriber).order_by(TelegramSubscriber.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_role(self, chat_id: int, role: str) -> bool:
        sub = await self.get_subscriber(chat_id)
        if not sub:
            return False
        sub.role = role
        await self.session.commit()
        return True

    async def set_permissions(self, chat_id: int, perms: List[str]) -> bool:
        sub = await self.get_subscriber(chat_id)
        if not sub:
            return False
        sub.permissions = perms
        await self.session.commit()
        return True
