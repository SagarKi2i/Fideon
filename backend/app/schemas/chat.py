from typing import Any, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    conversationId: Optional[str] = None
    modelId: Optional[str] = None
