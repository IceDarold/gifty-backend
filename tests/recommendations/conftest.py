import pytest
from unittest.mock import AsyncMock, MagicMock
import uuid
from typing import Dict, Any, List

@pytest.fixture
def mock_anthropic_service():
    mock = AsyncMock()
    mock.normalize_topics.return_value = ["Coffee", "Tech", "Books"]
    mock.classify_topic.return_value = {"is_wide": False, "refined_topic": "Specialty Coffee"}
    mock.generate_hypotheses.return_value = [
        {
            "title": "AeroPress Kit",
            "description": "Perfect for travel",
            "reasoning": "He likes coffee and travels",
            "primary_gap": "the_optimizer",
            "search_queries": ["aeropress kit", "travel coffee maker"]
        }
    ]
    mock.generate_hypotheses_bulk.return_value = {
        "Coffee": {
            "is_wide": False,
            "hypotheses": [
                {
                    "title": "Coffee Roasting Class",
                    "description": "Learn to roast",
                    "reasoning": "Deep dive into hobby",
                    "primary_gap": "permission_to_spend",
                    "search_queries": ["coffee roasting course"]
                }
            ]
        }
    }
    mock.generate_topic_hints.return_value = [
        {"text": "Does she like brewing at home?", "topic": "Home Brewing"}
    ]
    return mock

@pytest.fixture
def mock_intelligence_client():
    mock = AsyncMock()
    mock.get_embeddings.return_value = [[0.1] * 1536]
    mock.rerank.return_value = [0.95, 0.8, 0.7]
    return mock

@pytest.fixture
def mock_notification_service():
    mock = AsyncMock()
    mock.notify.return_value = True
    return mock

@pytest.fixture
def mock_session_storage():
    mock = AsyncMock()
    # Logic will use actual models mostly, but we mock the save/load
    return mock

@pytest.fixture
def mock_recipient_service():
    mock = AsyncMock()
    return mock
