from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

from recommendations.models import QuizAnswers, RecommendationSession
from app.services.dialogue_manager import DialogueManager
from app.services.ai_reasoning_service import AIReasoningService
from app.services.recommendation import RecommendationService
from app.db import get_db
from app.services.session_storage import get_session_storage
from app.services.embeddings import get_embedding_service

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

async def get_dialogue_manager(
    db_session = Depends(get_db)
):
    ai_service = AIReasoningService(db=db_session)
    emb = get_embedding_service()
    rec = RecommendationService(db_session, emb)
    storage = get_session_storage()
    return DialogueManager(ai_service, rec, storage, db=db_session)

class InteractionRequest(BaseModel):
    session_id: str
    action: str
    value: Optional[str] = None
    metadata: dict = {}

@router.post("/init", response_model=RecommendationSession)
async def init_discovery(
    quiz: QuizAnswers,
    user_id: Optional[str] = None,
    manager: DialogueManager = Depends(get_dialogue_manager)
):
    """Start the discovery dialogue."""
    import uuid as uuid_lib
    user_uuid = None
    if user_id:
        try:
            user_uuid = uuid_lib.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid user_id format: {user_id}")
            
    try:
        session = await manager.init_session(quiz, user_id=user_uuid)
        return session
    except Exception as e:
        logger.exception("Failed to initialize discovery session")
        raise HTTPException(status_code=500, detail="Internal server error during discovery initialization")

@router.post("/interact", response_model=RecommendationSession)
async def interact(
    req: InteractionRequest,
    manager: DialogueManager = Depends(get_dialogue_manager)
):
    """Unified interaction endpoint for dialogue steps and feedback."""
    try:
        session = await manager.interact(
            session_id=req.session_id,
            action=req.action,
            value=req.value,
            metadata=req.metadata
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Interaction failed for session {req.session_id}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/hypothesis/{hypothesis_id}/products")
async def get_hypothesis_products(
    hypothesis_id: str,
    manager: DialogueManager = Depends(get_dialogue_manager)
):
    """Fetch specific products for a hypothesis ID."""
    import uuid as uuid_lib
    try:
        h_uuid = uuid_lib.UUID(hypothesis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid hypothesis_id format: {hypothesis_id}")

    try:
        # 1. Get hypothesis from DB
        db_h = await manager.recipient_service.get_hypothesis(h_uuid)
        if not db_h:
            raise HTTPException(status_code=404, detail="Hypothesis not found")
        
        # 2. Get recipient/user budget context if possible (optional)
        max_price = None
        # ... logic for budget ...

        # 3. Generate products using recommendation service
        products = await manager.recommendation_service.get_deep_dive_products(
            search_queries=db_h.search_queries or [db_h.title],
            hypothesis_title=db_h.title,
            hypothesis_description=db_h.description,
            max_price=max_price
        )
        
        return products
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to fetch products for hypothesis {hypothesis_id}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/hypothesis/{hypothesis_id}/react")
async def react_to_hypothesis(
    hypothesis_id: str,
    reaction: str, # like, dislike, shortlist
    manager: DialogueManager = Depends(get_dialogue_manager)
):
    """Record user reaction to a hypothesis."""
    import uuid as uuid_lib
    try:
        h_uuid = uuid_lib.UUID(hypothesis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid hypothesis_id format: {hypothesis_id}")

    try:
        db_h = await manager.recipient_service.update_hypothesis_reaction(h_uuid, reaction)
        if not db_h:
            raise HTTPException(status_code=404, detail="Hypothesis not found")
        
        return {"status": "success", "hypothesis_id": str(db_h.id), "reaction": db_h.user_reaction}
    except Exception as e:
        logger.exception(f"Failed to record reaction for hypothesis {hypothesis_id}")
        raise HTTPException(status_code=500, detail="Internal server error")
