import zlib
import logging
from typing import Optional, Dict, List, Any
from app.core.logic_config import logic_config

logger = logging.getLogger(__name__)

class ExperimentService:
    @staticmethod
    def get_variant_for_session(session_id: str, experiment_id: str) -> Optional[str]:
        """
        Determines the variant for a given session and experiment using deterministic hashing.
        Returns variant ID (e.g., 'variant_a') or None if experiment is not active.
        """
        # 1. Find experiment config
        exp_config = None
        for exp in (getattr(logic_config, "experiments", []) or []):
            if exp.get("id") == experiment_id:
                exp_config = exp
                break
        
        if not exp_config or not exp_config.get("is_active"):
            return None
            
        # 2. Get variants list
        variants = list(exp_config.get("variants", {}).keys())
        if not variants:
            return None
            
        # 3. Deterministic bucketing
        # Hash session_id + experiment_id to ensure stable allocation
        combined = f"{session_id}:{experiment_id}"
        hash_val = zlib.adler32(combined.encode())
        index = hash_val % len(variants)
        
        return variants[index]

    @staticmethod
    def get_overrides(session_id: str) -> Dict[str, Any]:
        """
        Aggregates all overrides for active experiments for a given session.
        """
        overrides = {}
        active_experiments = [e for e in (getattr(logic_config, "experiments", []) or []) if e.get("is_active")]
        
        for exp in active_experiments:
            variant_id = ExperimentService.get_variant_for_session(session_id, exp["id"])
            if variant_id:
                variant_data = exp["variants"].get(variant_id, {})
                v_overrides = variant_data.get("overrides", {})
                overrides.update(v_overrides)
                # Store experiment/variant info for logging
                overrides["_experiment_id"] = exp["id"]
                overrides["_variant_id"] = variant_id
                
        return overrides
