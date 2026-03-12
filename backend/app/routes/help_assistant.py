from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.config import GROQ_MODEL_HELP
from app.services.llm import ensure_llm_configured, llm_stream

router = APIRouter()


@router.post("/api/help-assistant")
async def help_assistant(request: Request):
    ensure_llm_configured()
    body = await request.json()
    messages = body.get("messages", [])
    help_system_prompt = (
        "You are the Fideon Fabric AI Help Assistant. You help users understand and use the Fideon Fabric platform.\n\n"
        "Key platform features you should explain:\n"
        "- Pods: Specialized AI models for insurance, healthcare, banking, legal, and travel workflows\n"
        "- Marketplace: Where users browse and activate AI pods by domain\n"
        "- Playground: Interactive workspace to test and use activated pods with real inputs\n"
        "- Dashboard: Shows active pods, metrics (queries, success rate, response time), and recent activity\n"
        "- Document Retrieval: Connect to AMS systems (Applied Epic, AMS360, HawkSoft, EZLynx, QQ Catalyst) to retrieve policy documents\n"
        "- Quote Generation: Generate insurance quotes with coverage analysis\n"
        "- Policy Comparison: Compare policies side-by-side for coverage gaps\n"
        "- Claims FNOL: First Notice of Loss processing for claims\n"
        "- Pod Dashboard: Detailed analytics for each active pod\n"
        "- Submission Intake: Carrier-side submission triage with appetite matching\n"
        "- Claims Adjudication: Carrier-side claims processing with fraud detection\n\n"
        "Security: All data is encrypted, models can run locally for maximum privacy, enterprise-grade security.\n\n"
        "Keep responses concise (2-4 sentences max), helpful, and focused on the platform. "
        "Use bullet points only when listing multiple features. Be friendly and encouraging."
    )
    status, headers, stream = await llm_stream(
        {
            "model": GROQ_MODEL_HELP,
            "messages": [{"role": "system", "content": help_system_prompt}, *messages],
            "stream": True,
        }
    )
    return StreamingResponse(stream, status_code=status, headers=headers)
