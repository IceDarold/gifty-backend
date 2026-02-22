import uuid
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.recipient_service import RecipientService
from app.models import Recipient, Interaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recipients", tags=["recipients"])


# Schemas
class RecipientResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    name: Optional[str]
    relation: Optional[str]
    interests: List[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RecipientCreate(BaseModel):
    name: Optional[str] = None
    relation: Optional[str] = None
    interests: List[str] = []


class RecipientUpdate(BaseModel):
    name: Optional[str] = None
    interests: Optional[List[str]] = None


class InteractionResponse(BaseModel):
    id: uuid.UUID
    recipient_id: uuid.UUID
    session_id: str
    action_type: str
    target_type: str
    target_id: str
    value: Optional[str]
    metadata_json: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Endpoints
@router.get("/", response_model=List[RecipientResponse])
async def list_recipients(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all recipients for a user."""
    service = RecipientService(db)
    recipients = await service.get_user_recipients(user_id)
    return recipients


@router.get("/{recipient_id}", response_model=RecipientResponse)
async def get_recipient(
    recipient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific recipient by ID."""
    service = RecipientService(db)
    recipient = await service.get_recipient(recipient_id)
    
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    return recipient


@router.put("/{recipient_id}", response_model=RecipientResponse)
async def update_recipient(
    recipient_id: uuid.UUID,
    data: RecipientUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update recipient information."""
    service = RecipientService(db)
    recipient = await service.update_recipient(
        recipient_id=recipient_id,
        name=data.name,
        interests=data.interests
    )
    
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    return recipient


@router.get("/{recipient_id}/history", response_model=List[InteractionResponse])
async def get_recipient_history(
    recipient_id: uuid.UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get interaction history for a recipient."""
    service = RecipientService(db)
    
    # Verify recipient exists
    recipient = await service.get_recipient(recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    interactions = await service.get_recipient_interactions(recipient_id, limit=limit)
    return interactions
