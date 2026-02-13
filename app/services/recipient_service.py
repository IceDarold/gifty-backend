import uuid
import logging
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Recipient, Interaction
from recommendations.models import RecipientProfile, UserInteraction

logger = logging.getLogger(__name__)


class RecipientService:
    """Service for managing Recipients in the database."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_recipient(
        self,
        user_id: Optional[uuid.UUID],
        profile: RecipientProfile
    ) -> Recipient:
        """Create a new recipient in the database from a RecipientProfile."""
        recipient = Recipient(
            id=uuid.UUID(profile.id) if profile.id else uuid.uuid4(),
            user_id=user_id,
            name=profile.name,
            interests=profile.quiz_data.interests if profile.quiz_data else []
        )
        
        self.db.add(recipient)
        await self.db.commit()
        await self.db.refresh(recipient)
        
        logger.info(f"Created recipient {recipient.id} for user {user_id}")
        return recipient
    
    async def get_recipient(self, recipient_id: uuid.UUID) -> Optional[Recipient]:
        """Get a recipient by ID."""
        result = await self.db.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_recipients(self, user_id: uuid.UUID) -> List[Recipient]:
        """Get all recipients for a user."""
        result = await self.db.execute(
            select(Recipient)
            .where(Recipient.user_id == user_id)
            .order_by(Recipient.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update_recipient(
        self,
        recipient_id: uuid.UUID,
        name: Optional[str] = None,
        interests: Optional[List[str]] = None
    ) -> Optional[Recipient]:
        """Update recipient information."""
        recipient = await self.get_recipient(recipient_id)
        if not recipient:
            return None
        
        if name is not None:
            recipient.name = name
        if interests is not None:
            recipient.interests = interests
        
        await self.db.commit()
        await self.db.refresh(recipient)
        return recipient
    
    async def save_interaction(
        self,
        recipient_id: uuid.UUID,
        session_id: str,
        interaction: UserInteraction
    ) -> Interaction:
        """Save a user interaction to the database."""
        db_interaction = Interaction(
            recipient_id=recipient_id,
            session_id=session_id,
            action_type=interaction.type,
            target_type=interaction.target_type,
            target_id=interaction.target_id,
            value=interaction.value,
            metadata_json=interaction.metadata
        )
        
        self.db.add(db_interaction)
        await self.db.commit()
        await self.db.refresh(db_interaction)
        
        return db_interaction
    
    async def get_recipient_interactions(
        self,
        recipient_id: uuid.UUID,
        limit: int = 100
    ) -> List[Interaction]:
        """Get interaction history for a recipient."""
        result = await self.db.execute(
            select(Interaction)
            .where(Interaction.recipient_id == recipient_id)
            .order_by(Interaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def save_hypotheses(
        self,
        session_id: str,
        recipient_id: Optional[uuid.UUID],
        track_title: str,
        hypotheses: List[any] # List[recommendations.models.Hypothesis]
    ) -> List[any]: # List[app.models.Hypothesis]
        """Save AI-generated hypotheses to the database."""
        from app.models import Hypothesis
        
        db_hypos = []
        for h in hypotheses:
            db_h = Hypothesis(
                id=uuid.UUID(h.id) if h.id else uuid.uuid4(),
                session_id=session_id,
                recipient_id=recipient_id,
                track_title=track_title,
                title=h.title,
                description=h.description,
                reasoning=h.reasoning,
                search_queries=h.search_queries
            )
            self.db.add(db_h)
            db_hypos.append(db_h)
        
        await self.db.commit()
        for db_h in db_hypos:
            await self.db.refresh(db_h)
            
        return db_hypos

    async def get_hypothesis(self, hypothesis_id: uuid.UUID) -> Optional[any]:
        """Get a hypothesis by ID."""
        from app.models import Hypothesis
        result = await self.db.execute(
            select(Hypothesis).where(Hypothesis.id == hypothesis_id)
        )
        return result.scalar_one_or_none()

    async def update_hypothesis_reaction(
        self,
        hypothesis_id: uuid.UUID,
        reaction: str
    ) -> Optional[any]:
        """Update user reaction (like, dislike, shortlist) for a hypothesis."""
        db_h = await self.get_hypothesis(hypothesis_id)
        if not db_h:
            return None
        
        db_h.user_reaction = reaction
        await self.db.commit()
        await self.db.refresh(db_h)
        return db_h
