from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any

from pydantic import BaseModel, Field
from recommendations.models import QuizAnswers, GiftingGoal, EffortLevel, SessionMode, RecipientRelation

logger = logging.getLogger(__name__)

# --- GUTG Core Definitions ---

class GiftingGap(str, Enum):
    MIRROR = "the_mirror"        # I see who you are
    OPTIMIZER = "the_optimizer"  # I make your life smoother
    CATALYST = "the_catalyst"    # I support who you're becoming
    ANCHOR = "the_anchor"        # Our bond is real
    PERMISSION = "the_permission" # You're allowed to enjoy

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

class UserProfile(BaseModel):
    # The probabilistic profile
    scores: Dict[GiftingGap, float] = Field(default_factory=dict)
    subtype_scores: Dict[GapSubtype, float] = Field(default_factory=dict)
    
    # Meta-constraints
    required_effort: EffortLevel = EffortLevel.LOW
    deadline_days: Optional[int] = None
    
    # Session state
    viewed_ideas: List[str] = Field(default_factory=list)
    liked_ideas: List[str] = Field(default_factory=list)
    disliked_ideas: List[str] = Field(default_factory=list)

class GiftIdea(BaseModel):
    id: str
    title: str
    description: str
    primary_gap: GiftingGap
    subtypes: List[GapSubtype] = []
    
    # Meta-tags for filtering
    min_effort: EffortLevel = EffortLevel.LOW 
    is_custom: bool = False 
    
    search_queries: List[str]
    why_it_fits: str

# --- Engine Implementation ---

class GUTGEngine:
    def __init__(self):
        # Mock Idea Library
        self.idea_library = [
            GiftIdea(
                id="diy_scrapbook",
                title="Memories Scrapbook",
                description="A collection of your shared moments.",
                primary_gap=GiftingGap.ANCHOR,
                subtypes=[GapSubtype.TIME_CAPSULE],
                min_effort=EffortLevel.HIGH,
                is_custom=True,
                search_queries=["scrapbook kit", "photo album adhesive", "gel pens"],
                why_it_fits="Perfect for preserving your unique history."
            ),
            GiftIdea(
                id="premium_pen",
                title="Executive Pen",
                description="Status symbol for their desk.",
                primary_gap=GiftingGap.PERMISSION,
                subtypes=[GapSubtype.STATUS_QUIET_REWARD],
                min_effort=EffortLevel.NO_EFFORT,
                search_queries=["parker pen", "montblanc pen"],
                why_it_fits="A subtle nod to their professional success."
            ),
            GiftIdea(
                id="weighted_blanket",
                title="Deep Sleep Cocoon",
                description="Scientific comfort for better rest.",
                primary_gap=GiftingGap.OPTIMIZER,
                subtypes=[GapSubtype.COMFORT_REGULATOR],
                min_effort=EffortLevel.NO_EFFORT,
                search_queries=["weighted blanket", "gravity blanket"],
                why_it_fits="They are tired; this is a 'license to rest'."
            )
        ]

    def initial_scoring(self, quiz: QuizAnswers) -> UserProfile:
        """
        Calculates GUTG weights based on ALL quiz answers including Intent.
        """
        profile = UserProfile(
            scores={}, 
            subtype_scores={},
            required_effort=quiz.effort_level,
            deadline_days=quiz.deadline_days
        )
        
        # 1. Base Logic from Interests/Vibe
        vibe = (quiz.vibe or "").lower()
        if 'cozy' in vibe:
            self._boost(profile, GiftingGap.OPTIMIZER, 0.4)
            self._boost_sub(profile, GapSubtype.COMFORT_REGULATOR, 0.5)
        
        # 2. Intent Logic
        if quiz.gifting_goal == GiftingGoal.IMPRESS:
            self._boost(profile, GiftingGap.MIRROR, 0.3)
            self._boost(profile, GiftingGap.PERMISSION, 0.2)
            self._boost_sub(profile, GapSubtype.STATUS_QUIET_REWARD, 0.4)
            
        elif quiz.gifting_goal == GiftingGoal.CARE:
            self._boost(profile, GiftingGap.OPTIMIZER, 0.3)
            self._boost(profile, GiftingGap.ANCHOR, 0.2)
            self._boost_sub(profile, GapSubtype.COMFORT_REGULATOR, 0.4)
            
        elif quiz.gifting_goal == GiftingGoal.PROTOCOL:
            self._boost(profile, GiftingGap.PERMISSION, 0.4) 
            if GiftingGap.MIRROR in profile.scores:
                profile.scores[GiftingGap.MIRROR] *= 0.5 
                
        # 3. Relationship Logic
        if quiz.relationship == RecipientRelation.COLLEAGUE:
            self._boost(profile, GiftingGap.OPTIMIZER, 0.3)
            profile.scores[GiftingGap.ANCHOR] = 0.0
            
        elif quiz.relationship in [RecipientRelation.PARTNER, RecipientRelation.BEST_FRIEND]:
            self._boost(profile, GiftingGap.ANCHOR, 0.5)

        return profile

    def recommend_ideas(self, profile: UserProfile, limit: int = 3) -> List[GiftIdea]:
        """
        Ranking with Filters (Effort, Deadline)
        """
        scored_ideas = []
        
        for idea in self.idea_library:
            if self._is_effort_too_high(user_effort=profile.required_effort, idea_effort=idea.min_effort):
                continue
            
            score = 0.0
            score += profile.scores.get(idea.primary_gap, 0.0) * 1.0
            for st in idea.subtypes:
                score += profile.subtype_scores.get(st, 0.0) * 0.5
            
            scored_ideas.append((score, idea))
        
        scored_ideas.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored_ideas[:limit]]

    def _boost(self, profile: UserProfile, gap: GiftingGap, amount: float):
        profile.scores[gap] = min(1.0, profile.scores.get(gap, 0.0) + amount)

    def _boost_sub(self, profile: UserProfile, sub: GapSubtype, amount: float):
        profile.subtype_scores[sub] = min(1.0, profile.subtype_scores.get(sub, 0.0) + amount)

    def _is_effort_too_high(self, user_effort: EffortLevel, idea_effort: EffortLevel) -> bool:
        levels = {
            EffortLevel.NO_EFFORT: 0,
            EffortLevel.LOW: 1,
            EffortLevel.MEDIUM: 2,
            EffortLevel.HIGH: 3
        }
        return levels[idea_effort] > levels.get(user_effort, 1)
