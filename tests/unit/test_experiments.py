import pytest
import zlib
from app.services.experiments import ExperimentService
from app.core.logic_config import logic_config
from unittest.mock import patch

def test_deterministic_bucketing():
    session_id_1 = "session_123"
    session_id_2 = "session_456"
    exp_id = "ai_model_v2_test"
    
    # Mock experiments in logic_config
    mock_exp = [
        {
            "id": exp_id,
            "is_active": True,
            "variants": {
                "variant_a": {"name": "A", "overrides": {}},
                "variant_b": {"name": "B", "overrides": {}}
            }
        }
    ]
    
    with patch.object(logic_config, "experiments", mock_exp):
        v1 = ExperimentService.get_variant_for_session(session_id_1, exp_id)
        v1_again = ExperimentService.get_variant_for_session(session_id_1, exp_id)
        v2 = ExperimentService.get_variant_for_session(session_id_2, exp_id)
        
        # Stability check
        assert v1 == v1_again
        assert v1 in ["variant_a", "variant_b"]
        assert v2 in ["variant_a", "variant_b"]

def test_overrides_aggregation():
    session_id = "test_session"
    exp_id = "test_exp"
    
    # Mock experiment with specific overrides
    mock_exp = [
        {
            "id": exp_id,
            "is_active": True,
            "variants": {
                "variant_a": {"name": "A", "overrides": {"llm_model_fast": "model_a"}},
                "variant_b": {"name": "B", "overrides": {"llm_model_fast": "model_b"}}
            }
        }
    ]
    
    with patch.object(logic_config, "experiments", mock_exp):
        overrides = ExperimentService.get_overrides(session_id)
        
        assert "_experiment_id" in overrides
        assert "_variant_id" in overrides
        assert overrides["_experiment_id"] == exp_id
        assert overrides["llm_model_fast"] in ["model_a", "model_b"]

def test_inactive_experiment():
    session_id = "test_session"
    exp_id = "inactive_exp"
    
    mock_exp = [
        {
            "id": exp_id,
            "is_active": False,
            "variants": {"v1": {}}
        }
    ]
    
    with patch.object(logic_config, "experiments", mock_exp):
        v = ExperimentService.get_variant_for_session(session_id, exp_id)
        assert v is None
        
        overrides = ExperimentService.get_overrides(session_id)
        assert overrides == {}
