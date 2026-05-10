from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Domain(BaseModel):
    id: str
    display_name: str
    description: Optional[str] = None
    rag_collection: Optional[str] = None
    default_model_adapter: Optional[str] = None
    data_path: Optional[str] = None
    is_active: bool = True


class Agent(BaseModel):
    id: str
    display_name: str
    domain_id: str
    category: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    output_schema: Optional[Dict[str, Any]] = None
    rag_collection_override: Optional[str] = None
    model_adapter_override: Optional[str] = None
    tools: Optional[List[str]] = None
    is_active: bool = True


class DocumentInput(BaseModel):
    id: str
    text: str


class AgentRunRequest(BaseModel):
    query: str
    documents: Optional[List[DocumentInput]] = None
    extra_payload: Optional[Dict[str, Any]] = None

