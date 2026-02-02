from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Уникальный UUID пользователя")
    name: Optional[str] = Field(None, description="Имя пользователя")
    email: Optional[str] = Field(None, description="E-mail")
    avatar_url: Optional[str] = Field(None, description="URL аватарки")
