from __future__ import annotations
from typing import Optional, List, Sequence
from sqlalchemy import select, update, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import TelegramSubscriber

class TelegramRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_subscriber(self, chat_id: int) -> Optional[TelegramSubscriber]:
        stmt = select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
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
