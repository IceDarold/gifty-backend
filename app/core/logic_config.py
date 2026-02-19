import os
import yaml
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class RecommendationSettings(BaseModel):
    budget_margin_fraction: float = 0.1
    items_per_query: int = 4
    max_queries_for_preview: int = 3
    rerank_candidate_limit: int = 15

class LLMSettings(BaseModel):
    default_provider: str = "anthropic"
    model_fast: str = "claude-3-haiku-20240307"
    model_smart: str = "claude-3-5-sonnet-20240620"
    model_embedding: str = "bge-m3"
    embedding_provider: str = "intelligence_api"  # Options: intelligence_api, runpod, together

class FeatureToggles(BaseModel):
    use_runpod_for_high_priority: bool = True
    enable_external_workers: bool = True

class LogicConfig(BaseModel):
    """
    Centralized Business Logic Configuration.
    Loads from configs/logic.yaml with hierarchy:
    1. Static Defaults (in code)
    2. YAML file (configs/logic.yaml)
    3. Environment Overrides (optional, if we want to support them)
    """
    recommendation: RecommendationSettings = Field(default_factory=RecommendationSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    features: FeatureToggles = Field(default_factory=FeatureToggles)
    experiments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    @classmethod
    def load(cls) -> "LogicConfig":
        # Paths to look for config
        config_path = os.environ.get("LOGIC_CONFIG_PATH", "configs/logic.yaml")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config_dict = yaml.safe_load(f) or {}
                return cls.model_validate(config_dict)
            except Exception as e:
                logger.error(f"Failed to load logic config from {config_path}: {e}")
        
        logger.info(f"Using default logic configuration (file not found: {config_path})")
        return cls()

# Global instance
logic_config = LogicConfig.load()

# For backward compatibility with existing code
# These aliases allow existing code like `logic_config.model_fast` to work
def _patch_backward_compatibility(instance: LogicConfig):
    # This is a bit hacky but keeps existing code working without massive refactoring
    object.__setattr__(instance, "model_fast", instance.llm.model_fast)
    object.__setattr__(instance, "model_smart", instance.llm.model_smart)
    object.__setattr__(instance, "model_embedding", instance.llm.model_embedding)
    object.__setattr__(instance, "items_per_query", instance.recommendation.items_per_query)
    object.__setattr__(instance, "max_queries_for_preview", instance.recommendation.max_queries_for_preview)
    object.__setattr__(instance, "rerank_candidate_limit", instance.recommendation.rerank_candidate_limit)
    object.__setattr__(instance, "budget_margin_fraction", instance.recommendation.budget_margin_fraction)

_patch_backward_compatibility(logic_config)
