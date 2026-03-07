from abc import ABC, abstractmethod
from datetime import date, datetime
import json
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: str
    content: str

class LLMResponse(BaseModel):
    content: str
    raw_response: Any = None
    usage: Dict[str, int] = Field(default_factory=dict)
    provider_request_id: Optional[str] = None
    finish_reason: Optional[str] = None


def _json_default(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple, set)):
        return list(value)
    for attr in ("model_dump", "to_dict", "dict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                if attr == "model_dump":
                    return method(mode="json")
                return method()
            except TypeError:
                return method()
            except Exception:
                continue
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def serialize_raw_response(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    try:
        return json.loads(json.dumps(value, default=_json_default, ensure_ascii=False))
    except Exception:
        return {"_raw": str(value)}


def normalize_usage(usage: Optional[Any], raw_response: Optional[Any] = None) -> Dict[str, int]:
    if usage is None and raw_response is None:
        return {}
    if usage is None:
        payload = serialize_raw_response(raw_response)
        if isinstance(payload, dict):
            usage = payload.get("usage") or payload.get("usage_metadata")
    if not isinstance(usage, dict):
        usage = serialize_raw_response(usage)
    if not isinstance(usage, dict):
        usage = {}

    def _coerce_int(*keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except Exception:
                continue
        return 0

    prompt_tokens = _coerce_int(
        "prompt_tokens",
        "input_tokens",
        "prompt_token_count",
        "input_token_count",
    )
    completion_tokens = _coerce_int(
        "completion_tokens",
        "output_tokens",
        "completion_token_count",
        "output_token_count",
        "candidates_token_count",
    )
    total_tokens = _coerce_int("total_tokens", "total_token_count")
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens

    normalized = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }

    for source_key, target_key in (
        ("cached_tokens", "cached_tokens"),
        ("cached_input_tokens", "cached_tokens"),
        ("cache_read_input_tokens", "cached_tokens"),
        ("reasoning_tokens", "reasoning_tokens"),
        ("reasoning_output_tokens", "reasoning_tokens"),
        ("thoughts_token_count", "reasoning_tokens"),
    ):
        value = _coerce_int(source_key)
        if value > 0:
            normalized[target_key] = value

    return normalized


def extract_provider_request_id(raw_response: Any, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    payload = serialize_raw_response(raw_response)
    if isinstance(payload, dict):
        for key in ("id", "request_id", "response_id"):
            value = payload.get(key)
            if value:
                return str(value)
    return None


def extract_finish_reason(raw_response: Any, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    payload = serialize_raw_response(raw_response)
    if isinstance(payload, dict):
        for key in ("finish_reason", "stop_reason"):
            value = payload.get(key)
            if value:
                return str(value)
        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                for key in ("finish_reason", "stop_reason"):
                    value = choice.get(key)
                    if value:
                        return str(value)
                message = choice.get("message")
                if isinstance(message, dict):
                    for key in ("finish_reason", "stop_reason"):
                        value = message.get(key)
                        if value:
                            return str(value)
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, dict):
                    value = candidate.get("finish_reason") or candidate.get("finishReason")
                    if value:
                        return str(value)
    return None

class LLMClient(ABC):
    """
    Abstract interface for LLM providers.
    """
    
    @abstractmethod
    async def generate_text(
        self, 
        messages: List[Message], 
        model: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stops: Optional[List[str]] = None,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Generates text based on the provided messages.
        """
        pass
