from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# --- Core Enums ---

class Language(str, Enum):
    RU = "ru"
    EN = "en"

class RecipientRelation(str, Enum):
    PARTNER = "partner"
    FRIEND = "friend"
    BEST_FRIEND = "best_friend"
    RELATIVE = "relative"
    COLLEAGUE = "colleague"
    CHILD = "child"
    UNKNOWN = "unknown"

class EffortLevel(str, Enum):
    NO_EFFORT = "no_effort"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class GiftingGoal(str, Enum):
    IMPRESS = "impress"
    CARE = "care"
    PROTOCOL = "protocol"
    APOLOGY = "apology"
    JOKE = "joke"
    GROWTH = "growth"

class SessionMode(str, Enum):
    QUICK_FIX = "quick_fix"
    THOUGHTFUL = "thoughtful"
    DEEP_DIVE = "deep_dive"

class GiftingGap(str, Enum):
    MIRROR = "the_mirror"
    OPTIMIZER = "the_optimizer"
    CATALYST = "the_catalyst"
    ANCHOR = "the_anchor"
    PERMISSION = "the_permission"

class GapSubtype(str, Enum):
    # Mirror
    FANATIC = "fanatic"
    AESTHETIC = "aesthetic"
    TASTE_TOKEN = "taste_token"
    # Optimizer
    UPGRADE = "upgrade"
    FIX = "fix"
    COMFORT_REGULATOR = "comfort_regulator"
    # Catalyst
    STARTER = "starter"
    ACCELERATOR = "accelerator"
    # Anchor
    TIME_CAPSULE = "time_capsule" 
    RITUAL_BUILDER = "ritual_builder"
    # Permission
    QUIET_PREMIUM = "quiet_premium"
    SENSORY_TREAT = "sensory_treat"
    STATUS_QUIET_REWARD = "status_quiet_reward"

# --- Core Models ---

class GapFinding(BaseModel):
    gap: GiftingGap
    pain_point: str        # The specific problem detected (e.g., "old coffee machine")
    evidence: str          # How we know this (e.g., "user mentioned fatigue")
    confidence: float = 1.0

class UserInteraction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str # like, dislike, view, purchase, comment
    timestamp: float
    target_id: str # hypothesis_id or product_id
    target_type: str # hypothesis, product
    value: Optional[str] = None # comment text or specific value
    metadata: Dict[str, Any] = Field(default_factory=dict)

class QuizAnswers(BaseModel):
    """User input from the initial quiz/questionnaire."""
    # --- Context (Meta) ---
    relationship: Optional[RecipientRelation] = None
    gifting_goal: Optional[GiftingGoal] = None
    effort_level: EffortLevel = EffortLevel.LOW
    session_mode: SessionMode = SessionMode.THOUGHTFUL
    budget: Optional[int] = None
    deadline_days: Optional[int] = None  # How many days until gift is needed
    language: Language = Language.RU
    
    # --- Content (The "What") ---
    recipient_age: int
    recipient_gender: Optional[str] = None
    occasion: Optional[str] = None
    vibe: Optional[str] = None
    interests: List[str] = []
    interests_description: Optional[str] = None

class GiftDTO(BaseModel):
    id: str
    gift_id: Optional[str] = None # Added for compatibility with Catalog IDs
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    delivery_days: Optional[int] = None
    is_customizable: bool = False

# --- Dialogue Models ---

class DialogueStep(BaseModel):
    """A 'Probe' or question from the system."""
    question: str
    options: List[str] = []
    can_skip: bool = True
    context_tags: List[str] = []  # e.g. ["topic:coffee"]

class Hypothesis(BaseModel):
    """A concept card showing a direction."""
    id: str
    title: str
    description: str
    reasoning: str
    primary_gap: GiftingGap
    preview_products: List[GiftDTO] = []
    search_queries: List[str] = []

class TopicTrack(BaseModel):
    """A parallel discovery track for a specific topic."""
    topic_id: str
    topic_name: str
    status: str = "ready" # ready, loading, error, question
    title: Optional[str] = None
    preview_text: Optional[str] = None
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    question: Optional[DialogueStep] = None # If status is "question"

class RecipientResponse(BaseModel):
    """Simplified recipient info for the frontend."""
    id: str
    name: Optional[str] = None

class RecipientProfile(BaseModel):
    """
    Internal model for storing full recipient context in Redis/Cache.
    NOT returned directly to the frontend in this form.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: Optional[str] = None
    name: Optional[str] = None

    # Internal state
    quiz_data: Optional[QuizAnswers] = None
    findings: List[GapFinding] = Field(default_factory=list)
    interactions: List[UserInteraction] = Field(default_factory=list)
    liked_hypotheses: List[str] = Field(default_factory=list)
    liked_labels: List[str] = Field(default_factory=list)
    ignored_hypotheses: List[str] = Field(default_factory=list)
    ignored_labels: List[str] = Field(default_factory=list)
    shortlist: List[str] = Field(default_factory=list)
    
    required_effort: EffortLevel = EffortLevel.LOW
    budget: Optional[int] = None
    deadline_days: Optional[int] = None
    language: Language = Language.RU


class RecommendationSession(BaseModel):
    session_id: str
    recipient: RecipientResponse
    
    # Internal State (Excluded from API response, but saved in Redis)
    full_recipient: RecipientProfile = Field(exclude=True)
    topics: List[str] = Field(default_factory=list, exclude=True)
    language: Language = Field(default=Language.RU, exclude=True)
    
    # Parallel tracks (The main content)
    tracks: List[TopicTrack] = Field(default_factory=list)
    # Interaction Tracking
    liked_hypotheses: List[str] = Field(default_factory=list)
    ignored_hypotheses: List[str] = Field(default_factory=list)
    # Discovery Helpers
    topic_hints: List[Dict[str, str]] = Field(default_factory=list)
    
    # Navigation & State
    selected_topic_id: Optional[str] = None
    selected_hypothesis_id: Optional[str] = None
    
    # Fallback for questions (if not part of a specific track or for general session questions)
    current_probe: Optional[DialogueStep] = None
