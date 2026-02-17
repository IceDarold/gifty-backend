import json
import logging
import re
from typing import List, Dict, Any, Optional
from anthropic import AsyncAnthropic

from recommendations.models import GiftingGap, Hypothesis, DialogueStep, Language, UserInteraction, RecipientProfile
from app.prompts import registry
from app.core.logic_config import logic_config

logger = logging.getLogger(__name__)

class AnthropicService:
    def __init__(self, model: Optional[str] = None):
        # Use config if specific model not provided
        self.model_fast = logic_config.model_fast
        self.model_smart = logic_config.model_smart
        
        self.default_model = model or self.model_fast
        self.client = AsyncAnthropic()

    async def normalize_topics(self, topics: List[str], language: str = "ru") -> List[str]:
        """Cleans and standardizes raw user input topics."""
        if not topics:
            return []
            
        template = registry.get_prompt("normalize_topics")
        clean_topics = [self._sanitize_input(t) for t in topics]
        prompt = template.format(topics=json.dumps(clean_topics, ensure_ascii=False), language=language)
        
        response = await self.client.messages.create(
            model=self.default_model,
            max_tokens=1000,
            system=registry.get_prompt("system").format(language=language),
            messages=[{"role": "user", "content": prompt}]
        )
        return await self._extract_json(response.content[0].text)

    async def classify_topic(self, topic: str, quiz_data: Dict[str, Any], language: str = "ru") -> Dict[str, Any]:
        """Determines if a topic is 'wide' and needs branching."""
        template = registry.get_prompt("classify_topic")
        prompt = template.format(
            topic=self._sanitize_input(topic), 
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            language=language
        )
        
        response = await self.client.messages.create(
            model=self.model_fast,
            max_tokens=600,
            system=registry.get_prompt("system").format(language=language),
            messages=[{"role": "user", "content": prompt}]
        )
        return await self._extract_json(response.content[0].text)

    async def generate_hypotheses(
        self, 
        topic: str, 
        quiz_data: Dict[str, Any], 
        liked_concepts: List[str] = [],
        disliked_concepts: List[str] = [], 
        shown_concepts: List[str] = [],
        language: str = "ru"
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
        
        response = await self.client.messages.create(
            model=self.model_smart,
            max_tokens=1500,
            system=registry.get_prompt("system").format(language=language),
            messages=[{"role": "user", "content": prompt}]
        )
        return await self._extract_json(response.content[0].text)

    async def generate_personalized_probe(self, context_type: str, quiz_data: Dict[str, Any], topic: Optional[str] = None, language: str = "ru") -> Dict[str, Any]:
        """Generates a high-quality follow-up question when more info is needed."""
        prompt_name = f"personalized_probe_{context_type}"
        template = registry.get_prompt(prompt_name)
        
        prompt = template.format(
            topic=self._sanitize_input(topic or "general"),
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2)
        )

        response = await self.client.messages.create(
            model=self.model_fast,
            max_tokens=600,
            system=registry.get_prompt("system").format(language=language),
            messages=[{"role": "user", "content": prompt}]
        )
        return await self._extract_json(response.content[0].text)

    async def generate_hypotheses_bulk(
        self, 
        topics: List[str], 
        quiz_data: Dict[str, Any], 
        liked_concepts: List[str] = [],
        disliked_concepts: List[str] = [],
        language: str = "ru"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Generates GUTG hypotheses for MULTIPLE topics in a single API call."""
        template = registry.get_prompt("generate_hypotheses_bulk")
        clean_topics = [self._sanitize_input(t) for t in topics]
        prompt = template.format(
            topics_str=json.dumps(clean_topics, ensure_ascii=False),
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            liked_concepts=", ".join([self._sanitize_input(c) for c in liked_concepts]) if liked_concepts else "None",
            disliked_concepts=", ".join([self._sanitize_input(c) for c in disliked_concepts]) if disliked_concepts else "None",
            language=language
        )
        
        response = await self.client.messages.create(
            model=self.model_smart,
            max_tokens=2500,
            system=registry.get_prompt("system").format(language=language),
            messages=[{"role": "user", "content": prompt}]
        )
        return await self._extract_json(response.content[0].text)

    async def generate_topic_hints(self, quiz_data: Dict[str, Any], topics_explored: List[str], language: str = "ru") -> List[Dict[str, Any]]:
        """Generates 3-5 guiding questions to help user discover new topics."""
        template = registry.get_prompt("generate_topic_hints")
        prompt = template.format(
            quiz_json=json.dumps(self._sanitize_dict(quiz_data), ensure_ascii=False, indent=2),
            topics_explored=", ".join([self._sanitize_input(t) for t in topics_explored]) if topics_explored else "None"
        )
        
        response = await self.client.messages.create(
            model=self.model_fast,
            max_tokens=800,
            system=registry.get_prompt("system").format(language=language),
            messages=[{"role": "user", "content": prompt}]
        )
        data = await self._extract_json(response.content[0].text)
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
