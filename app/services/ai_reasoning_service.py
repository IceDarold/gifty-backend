import json
import logging
import re
import hashlib
from typing import List, Dict, Any, Optional

import time
from sqlalchemy.ext.asyncio import AsyncSession
from app.prompts import registry
from app.core.logic_config import logic_config
from app.services.llm.factory import LLMFactory
from app.services.llm.interface import (
    Message,
    LLMResponse,
    extract_finish_reason,
    extract_provider_request_id,
    normalize_usage,
    serialize_raw_response,
)
from app.services.llm.cost_estimator import estimate_cost
from app.services.llm.observability_store import get_or_create_payload, get_or_create_prompt_template
from app.services.experiments import ExperimentService
from app.models import LLMLog
from app.analytics_events.emitters import emit_event

logger = logging.getLogger(__name__)


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
_API_KEY_LIKE_RE = re.compile(r"\b(?:sk|gsk|phx|AIza|xoxb|xoxa|xapp|EAACEdEose0cBA)[-_A-Za-z0-9]{10,}\b")


def _redact_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    if not isinstance(text, str):
        return str(text)
    redacted = text
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _API_KEY_LIKE_RE.sub("[REDACTED_TOKEN]", redacted)
    # Basic header-style secrets
    redacted = re.sub(r"(?i)(authorization\\s*:\\s*bearer)\\s+[^\\s]+", r"\\1 [REDACTED_TOKEN]", redacted)
    return redacted


def _redact_messages(messages: List[Message]) -> List[dict]:
    out: List[dict] = []
    for m in messages:
        dump = m.model_dump()
        dump["content"] = _redact_text(dump.get("content"))
        out.append(dump)
    return out


def _hash_prompt(system_prompt: Optional[str], messages: List[Message]) -> str:
    h = hashlib.sha256()
    if system_prompt:
        h.update(system_prompt.encode("utf-8", errors="ignore"))
        h.update(b"\0")
    for m in messages:
        h.update(str(m.role).encode("utf-8", errors="ignore"))
        h.update(b"\0")
        h.update(str(m.content).encode("utf-8", errors="ignore"))
        h.update(b"\0")
    return h.hexdigest()


class AIReasoningService:
    """
    Service for AI-driven reasoning and logic, agnostic of the underlying LLM provider.
    Replaces the provider-specific AnthropicService.
    """
    def __init__(self, db: Optional[AsyncSession] = None, model: Optional[str] = None):
        self.db = db
        # Use config if specific model not provided
        self.model_fast = logic_config.model_fast
        self.model_smart = logic_config.model_smart
        
        self.default_model = model or self.model_fast
        # Get the configured LLM client
        self.llm_client = LLMFactory.get_client()

    async def _log_call(
        self, 
        call_type: str, 
        model: str, 
        response: Optional[LLMResponse],
        latency_ms: int,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        system_prompt_template_name: Optional[str] = None,
        system_prompt_template_content: Optional[str] = None,
        system_prompt_template_params: Optional[dict] = None,
        user_prompt_template_name: Optional[str] = None,
        user_prompt_template_content: Optional[str] = None,
        user_prompt_template_params: Optional[dict] = None,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        status: str = "ok",
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        params: Optional[dict] = None,
    ):
        """Asynchronously logs LLM call to database if session is available."""
        if not self.db:
            return

        try:
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            output_content = None
            raw_response = None
            finish_reason = None
            input_messages_payload_id = None

            if response is not None:
                raw_response = serialize_raw_response(response.raw_response)
                usage = normalize_usage(response.usage or {}, raw_response)
                prompt_tokens = int(usage.get("prompt_tokens") or 0)
                completion_tokens = int(usage.get("completion_tokens") or 0)
                total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
                output_content = response.content
                finish_reason = extract_finish_reason(raw_response, response.finish_reason)

            provider_request_id = extract_provider_request_id(raw_response, getattr(response, "provider_request_id", None))

            prompt_hash = _hash_prompt(system_prompt, messages)

            # Determine actual provider name
            provider_name = getattr(self.llm_client, "provider", logic_config.llm.default_provider)
            if hasattr(self.llm_client, "__class__"):
                class_name = self.llm_client.__class__.__name__.lower()
                if "groq" in class_name:
                    provider_name = "groq"
                elif "anthropic" in class_name:
                    provider_name = "anthropic"
                elif "gemini" in class_name:
                    provider_name = "gemini"
                elif "openrouter" in class_name:
                    provider_name = "openrouter"
                elif "together" in class_name:
                    provider_name = "together"

            system_template_id = None
            user_template_id = None
            output_payload_id = None
            raw_payload_id = None
            input_messages = [m.model_dump() for m in messages] if messages else None
            can_store_observability_payloads = hasattr(self.db, "execute")

            if can_store_observability_payloads and system_prompt_template_name and system_prompt_template_content:
                system_template_id = await get_or_create_prompt_template(
                    self.db,
                    name=system_prompt_template_name,
                    content=system_prompt_template_content,
                    kind="system",
                )

            if can_store_observability_payloads and user_prompt_template_name and user_prompt_template_content:
                user_template_id = await get_or_create_prompt_template(
                    self.db,
                    name=user_prompt_template_name,
                    content=user_prompt_template_content,
                    kind="user",
                )
                # Template already defines the user prompt; avoid duplicating raw input messages.
                input_messages = None

            if can_store_observability_payloads and output_content is not None:
                output_payload_id = await get_or_create_payload(
                    self.db, kind="output_text", content_text=output_content
                )

            if can_store_observability_payloads and raw_response is not None:
                raw_payload_id = await get_or_create_payload(self.db, kind="raw_response", content_json=raw_response)

            if can_store_observability_payloads and user_template_id is None and input_messages is not None:
                # Avoid duplicating large message arrays per log row.
                input_messages_payload_id = await get_or_create_payload(
                    self.db, kind="input_messages", content_json=input_messages
                )
                input_messages = None

            log = LLMLog(
                provider=provider_name,
                model=model,
                call_type=call_type,
                input_messages=input_messages,
                input_messages_payload_id=input_messages_payload_id,
                system_prompt=None if system_template_id else system_prompt,
                output_content=None if output_payload_id else output_content,
                system_prompt_template_id=system_template_id,
                system_prompt_params=system_prompt_template_params,
                user_prompt_template_id=user_template_id,
                user_prompt_params=user_prompt_template_params,
                output_payload_id=output_payload_id,
                raw_response_payload_id=raw_payload_id,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost_usd=await estimate_cost(model, prompt_tokens, completion_tokens),
                session_id=session_id,
                experiment_id=experiment_id,
                variant_id=variant_id,
                status=status,
                error_type=error_type,
                error_message=error_message,
                provider_request_id=provider_request_id,
                prompt_hash=prompt_hash,
                params=params,
            )
            self.db.add(log)
            await self.db.commit()

            await emit_event(
                event_type="llm.call_completed",
                source="api",
                session_id=session_id,
                dims={
                    "provider": provider_name,
                    "model": model,
                    "call_type": call_type,
                    "status": status,
                },
                metrics={
                    "total_tokens": float(total_tokens),
                    "latency_ms": float(latency_ms),
                    "cost_usd": float(log.cost_usd or 0.0),
                    "value": 1.0,
                },
                payload={
                    "experiment_id": experiment_id,
                    "variant_id": variant_id,
                    "error_type": error_type,
                },
            )
        except Exception as e:
            logger.error(f"Failed to log LLM call: {e}")

    async def _generate_with_logging(
        self,
        call_type: str,
        model: str,
        system_prompt: str,
        messages: List[Message],
        max_tokens: int = 1000,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        stops: Optional[List[str]] = None,
        json_mode: bool = False,
        system_prompt_template_name: Optional[str] = None,
        system_prompt_template_content: Optional[str] = None,
        system_prompt_template_params: Optional[dict] = None,
        user_prompt_template_name: Optional[str] = None,
        user_prompt_template_content: Optional[str] = None,
        user_prompt_template_params: Optional[dict] = None,
    ) -> Any:
        # A/B Testing Overrides
        experiment_id = None
        variant_id = None
        if session_id:
            overrides = ExperimentService.get_overrides(session_id)
            if overrides:
                # Override model if specified
                if "llm_model_fast" in overrides and model == self.model_fast:
                    model = overrides["llm_model_fast"]
                elif "llm_model_smart" in overrides and model == self.model_smart:
                    model = overrides["llm_model_smart"]
                
                experiment_id = overrides.get("_experiment_id")
                variant_id = overrides.get("_variant_id")

        start_time = time.time()
        params = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stops": stops,
            "json_mode": json_mode,
        }

        try:
            response = await self.llm_client.generate_text(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                stops=stops,
                json_mode=json_mode,
                system_prompt=system_prompt,
                messages=messages,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            await self._log_call(
                call_type,
                model,
                response,
                latency_ms,
                messages,
                system_prompt,
                system_prompt_template_name=system_prompt_template_name,
                system_prompt_template_content=system_prompt_template_content,
                system_prompt_template_params=system_prompt_template_params,
                user_prompt_template_name=user_prompt_template_name,
                user_prompt_template_content=user_prompt_template_content,
                user_prompt_template_params=user_prompt_template_params,
                session_id=session_id,
                experiment_id=experiment_id,
                variant_id=variant_id,
                status="ok",
                params=params,
            )

            return await self._extract_json(response.content)
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            await self._log_call(
                call_type,
                model,
                None,
                latency_ms,
                messages,
                system_prompt,
                system_prompt_template_name=system_prompt_template_name,
                system_prompt_template_content=system_prompt_template_content,
                system_prompt_template_params=system_prompt_template_params,
                user_prompt_template_name=user_prompt_template_name,
                user_prompt_template_content=user_prompt_template_content,
                user_prompt_template_params=user_prompt_template_params,
                session_id=session_id,
                experiment_id=experiment_id,
                variant_id=variant_id,
                status="error",
                error_type=type(e).__name__,
                error_message=str(e),
                params=params,
            )
            raise

    async def normalize_topics(self, topics: List[str], language: str = "ru", session_id: Optional[str] = None) -> List[str]:
        """Cleans and standardizes raw user input topics."""
        if not topics:
            return []
            
        template_name = "normalize_topics"
        template = registry.get_prompt(template_name)
        system_template_name = "system"
        system_template = registry.get_prompt(system_template_name)
        clean_topics = [self._sanitize_input(t) for t in topics]
        user_params = {"topics": json.dumps(clean_topics, ensure_ascii=False), "language": language}
        prompt = template.format(**user_params)
        system_params = {"language": language}
        system_prompt = system_template.format(**system_params)
        
        return await self._generate_with_logging(
            call_type="normalize_topics",
            model=self.default_model,
            system_prompt=system_prompt,
            messages=[Message(role="user", content=prompt)],
            session_id=session_id,
            system_prompt_template_name=system_template_name,
            system_prompt_template_content=system_template,
            system_prompt_template_params=system_params,
            user_prompt_template_name=template_name,
            user_prompt_template_content=template,
            user_prompt_template_params=user_params,
        )

    async def classify_topic(self, topic: str, quiz_data: Dict[str, Any], language: str = "ru", session_id: Optional[str] = None) -> Dict[str, Any]:
        """Determines if a topic is 'wide' and needs branching."""
        template_name = "classify_topic"
        template = registry.get_prompt(template_name)
        system_template_name = "system"
        system_template = registry.get_prompt(system_template_name)
        user_params = {
            "topic": self._sanitize_input(topic),
            "quiz_json": json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            "language": language,
        }
        prompt = template.format(**user_params)
        system_params = {"language": language}
        system_prompt = system_template.format(**system_params)
        
        return await self._generate_with_logging(
            call_type="classify_topic",
            model=self.model_fast,
            system_prompt=system_prompt,
            messages=[Message(role="user", content=prompt)],
            session_id=session_id,
            system_prompt_template_name=system_template_name,
            system_prompt_template_content=system_template,
            system_prompt_template_params=system_params,
            user_prompt_template_name=template_name,
            user_prompt_template_content=template,
            user_prompt_template_params=user_params,
        )

    async def generate_hypotheses(
        self, 
        topic: str, 
        quiz_data: Dict[str, Any], 
        liked_concepts: List[str] = [],
        disliked_concepts: List[str] = [], 
        shown_concepts: List[str] = [],
        language: str = "ru",
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generates 3-4 GUTG hypotheses for a topic using raw quiz data."""
        template_name = "generate_hypotheses"
        template = registry.get_prompt(template_name)
        system_template_name = "system"
        system_template = registry.get_prompt(system_template_name)
        user_params = {
            "topic": self._sanitize_input(topic),
            "quiz_json": json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            "liked_concepts": ", ".join([self._sanitize_input(c) for c in liked_concepts]) if liked_concepts else "None",
            "disliked_concepts": ", ".join([self._sanitize_input(c) for c in disliked_concepts]) if disliked_concepts else "None",
            "shown_concepts": ", ".join([self._sanitize_input(c) for c in shown_concepts]) if shown_concepts else "None",
        }
        prompt = template.format(**user_params)
        system_params = {"language": language}
        system_prompt = system_template.format(**system_params)
        
        return await self._generate_with_logging(
            call_type="generate_hypotheses",
            model=self.model_smart,
            system_prompt=system_prompt,
            messages=[Message(role="user", content=prompt)],
            max_tokens=1500,
            session_id=session_id,
            system_prompt_template_name=system_template_name,
            system_prompt_template_content=system_template,
            system_prompt_template_params=system_params,
            user_prompt_template_name=template_name,
            user_prompt_template_content=template,
            user_prompt_template_params=user_params,
        )

    async def generate_personalized_probe(self, context_type: str, quiz_data: Dict[str, Any], topic: Optional[str] = None, language: str = "ru", session_id: Optional[str] = None) -> Dict[str, Any]:
        """Generates a high-quality follow-up question when more info is needed."""
        prompt_name = f"personalized_probe_{context_type}"
        template = registry.get_prompt(prompt_name)
        system_template_name = "system"
        system_template = registry.get_prompt(system_template_name)
        user_params = {
            "topic": self._sanitize_input(topic or "general"),
            "quiz_json": json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
        }
        prompt = template.format(**user_params)
        system_params = {"language": language}
        system_prompt = system_template.format(**system_params)

        return await self._generate_with_logging(
            call_type=f"probe_{context_type}",
            model=self.model_fast,
            system_prompt=system_prompt,
            messages=[Message(role="user", content=prompt)],
            session_id=session_id,
            system_prompt_template_name=system_template_name,
            system_prompt_template_content=system_template,
            system_prompt_template_params=system_params,
            user_prompt_template_name=prompt_name,
            user_prompt_template_content=template,
            user_prompt_template_params=user_params,
        )

    async def generate_hypotheses_bulk(
        self, 
        topics: List[str], 
        quiz_data: Dict[str, Any], 
        liked_concepts: List[str] = [],
        disliked_concepts: List[str] = [], 
        language: str = "ru",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates hypotheses for multiple topics in one prompt."""
        template_name = "generate_hypotheses_bulk"
        template = registry.get_prompt(template_name)
        system_template_name = "system"
        system_template = registry.get_prompt(system_template_name)
        user_params = {
            "topics_str": json.dumps([self._sanitize_input(t) for t in topics], ensure_ascii=False),
            "quiz_json": json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            "liked_concepts": ", ".join([self._sanitize_input(c) for c in liked_concepts]) if liked_concepts else "None",
            "disliked_concepts": ", ".join([self._sanitize_input(c) for c in disliked_concepts]) if disliked_concepts else "None",
            "language": language,
        }
        prompt = template.format(**user_params)
        system_params = {"language": language}
        system_prompt = system_template.format(**system_params)
        
        return await self._generate_with_logging(
            call_type="generate_hypotheses_bulk",
            model=self.model_smart,
            system_prompt=system_prompt,
            messages=[Message(role="user", content=prompt)],
            max_tokens=2500,
            session_id=session_id,
            system_prompt_template_name=system_template_name,
            system_prompt_template_content=system_template,
            system_prompt_template_params=system_params,
            user_prompt_template_name=template_name,
            user_prompt_template_content=template,
            user_prompt_template_params=user_params,
        )

    async def generate_topic_hints(self, quiz_data: Dict[str, Any], topics_explored: List[str], language: str = "ru", session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generates 3-5 guiding questions to help user discover new topics."""
        template_name = "generate_topic_hints"
        template = registry.get_prompt(template_name)
        system_template_name = "system"
        system_template = registry.get_prompt(system_template_name)
        user_params = {
            "quiz_json": json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            "topics_explored": ", ".join([self._sanitize_input(t) for t in topics_explored]) if topics_explored else "None",
        }
        prompt = template.format(**user_params)
        system_params = {"language": language}
        system_prompt = system_template.format(**system_params)
        
        data = await self._generate_with_logging(
            call_type="generate_topic_hints",
            model=self.model_fast,
            system_prompt=system_prompt,
            messages=[Message(role="user", content=prompt)],
            session_id=session_id,
            system_prompt_template_name=system_template_name,
            system_prompt_template_content=system_template,
            system_prompt_template_params=system_params,
            user_prompt_template_name=template_name,
            user_prompt_template_content=template,
            user_prompt_template_params=user_params,
        )
        return data.get("hints", [])

    async def _extract_json(self, text: str) -> Any:
        """Helper to extract JSON from LLM response strings."""
        try:
            # Look for JSON block
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(text)
        except Exception as e:
            logger.error(f"Failed to parse JSON from response: {text[:200]}... Error: {e}")
            return {}

    def _sanitize_input(self, text: str, max_length: int = 500) -> str:
        """
        Prevents prompt injection by:
        1. Truncating overly long inputs.
        2. Detecting suspicious patterns.
        3. Escaping potential tag breakers.
        """
        if not text:
            return ""
        
        # 1. Truncate
        text = text[:max_length]

        # 2. Check for suspicious patterns
        if self._is_suspicious(text):
            logger.warning(f"Suspicious input detected: {text[:50]}...")
            # We don't block yet, but we sanitize more aggressively 
            # or could return a 'safe' placeholder if needed.
            # For now, just strip problematic characters.
            text = re.sub(r'[<>{}/]', '', text) 

        return text

    def _is_suspicious(self, text: str) -> bool:
        """Detects common prompt injection keywords/patterns."""
        patterns = [
            r"ignore previous instructions",
            r"system prompt",
            r"you are now",
            r"stop being",
            r"new task:",
            r"assistant:",
            r"user:",
            r"<system>",
            r"### SYSTEM"
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitizes all strings in a dictionary."""
        new_dict = {}
        for k, v in data.items():
            if isinstance(v, str):
                new_dict[k] = self._sanitize_input(v)
            elif isinstance(v, dict):
                new_dict[k] = self._sanitize_dict(v)
            elif isinstance(v, list):
                new_dict[k] = [self._sanitize_input(i) if isinstance(i, str) else i for i in v]
            else:
                new_dict[k] = v
        return new_dict
