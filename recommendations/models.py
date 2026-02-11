from __future__ import annotations

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class RecipientRelation(str, Enum):
    PARTNER = "partner"       # Spouse, BF/GF
    FRIEND = "friend"         # Close friend
    BEST_FRIEND = "best_friend"
    RELATIVE = "relative"     # Parent, Sibling
    COLLEAGUE = "colleague"
    CHILD = "child"
    UNKNOWN = "unknown"

class EffortLevel(str, Enum):
    NO_EFFORT = "no_effort"       # "Just click buy, wrapping included"
    LOW = "low"                   # "I can wrap it"
    MEDIUM = "medium"             # "I can write a card, assemble a small kit"
    HIGH = "high"                 # "I'm ready to organize a scavenger hunt"

class GiftingGoal(str, Enum):
    IMPRESS = "impress"           # "I want them to say WOW"
    CARE = "care"                 # "I want them to feel loved/rested"
    PROTOCOL = "protocol"         # "It's a obligation/formal"
    APOLOGY = "apology"           # "I messed up"
    JOKE = "joke"                 # "Funny/Gag gift"
    GROWTH = "growth"             # "Support their hobby/work"

class SessionMode(str, Enum):
    QUICK_FIX = "quick_fix"       # "I need something NOW"
    THOUGHTFUL = "thoughtful"     # "I have 10-15 mins"
    DEEP_DIVE = "deep_dive"       # "I want to explore options"

class QuizAnswers(BaseModel):
    # --- Context (Meta) ---
    relationship: Optional[RecipientRelation] = None
    gifting_goal: Optional[GiftingGoal] = None
    effort_level: EffortLevel = EffortLevel.LOW
    session_mode: SessionMode = SessionMode.THOUGHTFUL
    budget: Optional[int] = None
    deadline_days: Optional[int] = None  # How many days until gift is needed
    
    # --- Content (The "What") ---
    recipient_age: int
    recipient_gender: Optional[str] = None
    occasion: Optional[str] = None
    vibe: Optional[str] = None
    interests: List[str] = []
    interests_description: Optional[str] = None

class GiftDTO(BaseModel):
    # Existing fields...
    id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    
    # New metadata fields likely needed later
    delivery_days: Optional[int] = None
    is_customizable: bool = False
