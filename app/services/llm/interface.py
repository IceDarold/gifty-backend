from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str

class LLMResponse(BaseModel):
    content: str
    raw_response: Any = None
    usage: Dict[str, int] = {}

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
