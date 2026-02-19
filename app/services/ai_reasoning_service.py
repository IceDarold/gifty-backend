import json
import logging
import re
from typing import List, Dict, Any, Optional

import time
from sqlalchemy.ext.asyncio import AsyncSession
from app.prompts import registry
from app.core.logic_config import logic_config
from app.services.llm.factory import LLMFactory
from app.services.llm.interface import Message, LLMResponse
from app.services.llm.cost_estimator import estimate_cost
from app.services.experiments import ExperimentService
from app.models import LLMLog

logger = logging.getLogger(__name__)

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
        response: LLMResponse, 
        latency_ms: int,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        variant_id: Optional[str] = None
    ):
        """Asynchronously logs LLM call to database if session is available."""
        if not self.db:
            return
            
        try:
            prompt_tokens = response.usage.get("prompt_tokens", 0)
            completion_tokens = response.usage.get("completion_tokens", 0)
            total_tokens = response.usage.get("total_tokens", prompt_tokens + completion_tokens)
            
            # Determine actual provider name
            provider_name = getattr(self.llm_client, "provider", logic_config.llm.default_provider)
            if hasattr(self.llm_client, "__class__"):
                class_name = self.llm_client.__class__.__name__.lower()
                if "groq" in class_name: provider_name = "groq"
                elif "anthropic" in class_name: provider_name = "anthropic"
                elif "gemini" in class_name: provider_name = "gemini"

            log = LLMLog(
                provider=provider_name,
                model=model,
                call_type=call_type,
                input_messages=[m.model_dump() for m in messages],
                system_prompt=system_prompt,
                output_content=response.content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost_usd=await estimate_cost(model, prompt_tokens, completion_tokens),
                session_id=session_id,
                experiment_id=experiment_id,
                variant_id=variant_id
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log LLM call: {e}")

    async def _generate_with_logging(
        self,
        call_type: str,
        model: str,
        system_prompt: str,
        messages: List[Message],
        max_tokens: int = 1000,
        session_id: Optional[str] = None
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
        response = await self.llm_client.generate_text(
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=messages
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log in fire-and-forget style
        await self._log_call(
            call_type, model, response, latency_ms, messages, system_prompt, 
            session_id=session_id, experiment_id=experiment_id, variant_id=variant_id
        )
        
        return await self._extract_json(response.content)

    async def normalize_topics(self, topics: List[str], language: str = "ru", session_id: Optional[str] = None) -> List[str]:
        """Cleans and standardizes raw user input topics."""
        if not topics:
            return []
            
        template = registry.get_prompt("normalize_topics")
        clean_topics = [self._sanitize_input(t) for t in topics]
        prompt = template.format(topics=json.dumps(clean_topics, ensure_ascii=False), language=language)
        
        return await self._generate_with_logging(
            call_type="normalize_topics",
            model=self.default_model,
            system_prompt=registry.get_prompt("system").format(language=language),
            messages=[Message(role="user", content=prompt)],
            session_id=session_id
        )

    async def classify_topic(self, topic: str, quiz_data: Dict[str, Any], language: str = "ru", session_id: Optional[str] = None) -> Dict[str, Any]:
        """Determines if a topic is 'wide' and needs branching."""
        template = registry.get_prompt("classify_topic")
        prompt = template.format(
            topic=self._sanitize_input(topic), 
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            language=language
        )
        
        return await self._generate_with_logging(
            call_type="classify_topic",
            model=self.model_fast,
            system_prompt=registry.get_prompt("system").format(language=language),
            messages=[Message(role="user", content=prompt)],
            session_id=session_id
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
        template = registry.get_prompt("generate_hypotheses")
        prompt = template.format(
            topic=self._sanitize_input(topic), 
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            liked_concepts=", ".join([self._sanitize_input(c) for c in liked_concepts]) if liked_concepts else "None",
            disliked_concepts=", ".join([self._sanitize_input(c) for c in disliked_concepts]) if disliked_concepts else "None",
            shown_concepts=", ".join([self._sanitize_input(c) for c in shown_concepts]) if shown_concepts else "None"
        )
        
        return await self._generate_with_logging(
            call_type="generate_hypotheses",
            model=self.model_smart,
            system_prompt=registry.get_prompt("system").format(language=language),
            messages=[Message(role="user", content=prompt)],
            max_tokens=1500,
            session_id=session_id
        )

    async def generate_personalized_probe(self, context_type: str, quiz_data: Dict[str, Any], topic: Optional[str] = None, language: str = "ru", session_id: Optional[str] = None) -> Dict[str, Any]:
        """Generates a high-quality follow-up question when more info is needed."""
        prompt_name = f"personalized_probe_{context_type}"
        template = registry.get_prompt(prompt_name)
        
        prompt = template.format(
            topic=self._sanitize_input(topic or "general"),
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2)
        )

        return await self._generate_with_logging(
            call_type=f"probe_{context_type}",
            model=self.model_fast,
            system_prompt=registry.get_prompt("system").format(language=language),
            messages=[Message(role="user", content=prompt)],
            session_id=session_id
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
        template = registry.get_prompt("generate_hypotheses_bulk")
        prompt = template.format(
            topics_str=json.dumps([self._sanitize_input(t) for t in topics], ensure_ascii=False),
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            liked_concepts=", ".join([self._sanitize_input(c) for c in liked_concepts]) if liked_concepts else "None",
            disliked_concepts=", ".join([self._sanitize_input(c) for c in disliked_concepts]) if disliked_concepts else "None"
        )
        
        return await self._generate_with_logging(
            call_type="generate_hypotheses_bulk",
            model=self.model_smart,
            system_prompt=registry.get_prompt("system").format(language=language),
            messages=[Message(role="user", content=prompt)],
            max_tokens=2500,
            session_id=session_id
        )

    async def generate_topic_hints(self, quiz_data: Dict[str, Any], topics_explored: List[str], language: str = "ru", session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generates 3-5 guiding questions to help user discover new topics."""
        template = registry.get_prompt("generate_topic_hints")
        prompt = template.format(
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            topics_explored=", ".join([self._sanitize_input(t) for t in topics_explored]) if topics_explored else "None"
        )
        
        data = await self._generate_with_logging(
            call_type="generate_topic_hints",
            model=self.model_fast,
            system_prompt=registry.get_prompt("system").format(language=language),
            messages=[Message(role="user", content=prompt)],
            session_id=session_id
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
