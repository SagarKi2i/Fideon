from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging

from app.schemas.agents import AgentRunRequest
from LLM.rag import generator as rag_generator

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger("fideon.agents")


@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, body: AgentRunRequest):
    """
    Generic entrypoint for all configured agents.

    This wires the agent/domain catalogs into the RAG pipeline and then
    streams the response from the backend LLM fallback chain.

    If `documents` are provided in the request body, the RAG layer will
    restrict retrieval to those documents only (no persistent index).
    """
    try:
        extra_payload = body.extra_payload or {}
        if body.documents is not None:
            logger.info(
                "Agents[run] agent_id=%s query_len=%d documents=%d",
                agent_id,
                len(body.query or ""),
                len(body.documents),
            )
            extra_payload = {
                **extra_payload,
                "documents": [doc.model_dump() for doc in body.documents],
            }
        else:
            logger.info(
                "Agents[run] agent_id=%s query_len=%d documents=0",
                agent_id,
                len(body.query or ""),
            )

        stream = await rag_generator.generate_answer(
            agent_id=agent_id,
            query=body.query,
            extra_payload=extra_payload,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Agents[run] unexpected error for agent_id=%s", agent_id)
        raise HTTPException(status_code=500, detail=str(exc))

    return StreamingResponse(stream, media_type="text/event-stream")

