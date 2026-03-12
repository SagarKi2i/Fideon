from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.core.config import GROQ_MODEL_CHAT
from app.core.supabase import postgrest_insert, verify_user
from app.schemas.chat import ChatRequest
from app.services.llm import ensure_llm_configured, llm_stream

router = APIRouter()


@router.post("/api/chat")
async def chat(req: ChatRequest, authorization: Optional[str] = Header(default=None)):
    ensure_llm_configured()
    user = await verify_user(authorization)

    system_prompt = "You are a helpful AI assistant in the Fideon Fabric platform."
    if req.modelId:
        domain_prompts = {
            "insurance": "You are an insurance domain expert. Help users analyze policies, compare coverage, identify exclusions, and answer insurance-related questions with accuracy and clarity.",
            "healthcare": "You are a healthcare AI assistant. Help with pre-authorization, clinical summaries, medical Q&A, and diagnosis support. Provide accurate medical information.",
            "banking": "You are a banking and finance expert. Assist with KYC analysis, compliance checking, risk assessment, and fraud detection.",
            "legal": "You are a legal AI assistant. Help review contracts, identify clauses, answer legal questions, and assess risks in legal documents.",
            "travel": "You are a travel knowledge expert. Assist with itinerary planning, visa requirements, destination information, and travel recommendations.",
        }
        system_prompt = domain_prompts.get(req.modelId, system_prompt)

    if req.conversationId and req.messages:
        try:
            await postgrest_insert(
                "chat_messages",
                {
                    "conversation_id": req.conversationId,
                    "role": "user",
                    "content": req.messages[-1].get("content", ""),
                    "user_id": user.get("id"),
                },
            )
        except Exception:
            pass

    status, headers, stream = await llm_stream(
        {
            "model": GROQ_MODEL_CHAT,
            "messages": [{"role": "system", "content": system_prompt}, *req.messages],
            "stream": True,
        }
    )
    return StreamingResponse(stream, status_code=status, headers=headers)
