"""
High‑level RAG generator.

Glues together:
- domain / agent catalogs (Supabase)
- retriever
- prompt builder
- backend LLM fallback chain (app.services.llm.llm_stream)
"""

import logging
from typing import Dict, Any, AsyncGenerator

from fastapi import HTTPException

from app.core import supabase
from app.core.config import DEFAULT_LLM_MODEL
from app.services import llm as llm_service
from LLM.rag import prompt_builder, retriever


logger = logging.getLogger("fideon.rag")


async def _load_agent_and_domain(agent_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    agents = await supabase.postgrest_get(
        "agent_catalog",
        f"id=eq.{agent_id}&is_active=eq.true&select=*",
    )
    if not agents:
        raise HTTPException(status_code=404, detail="Agent not found or inactive")
    agent = agents[0]

    domain_id = agent.get("domain_id")
    if not domain_id:
        raise HTTPException(status_code=500, detail="Agent missing domain_id")

    domains = await supabase.postgrest_get(
        "domain_catalog",
        f"id=eq.{domain_id}&is_active=eq.true&select=*",
    )
    if not domains:
        raise HTTPException(status_code=500, detail="Domain not found or inactive")
    domain = domains[0]
    logger.info(
        "RAG[agent] loaded agent_id=%s domain_id=%s rag_collection=%s",
        agent_id,
        domain_id,
        agent.get("rag_collection_override") or domain.get("rag_collection"),
    )
    return agent, domain


async def generate_answer(
    agent_id: str,
    query: str,
    *,
    extra_payload: Dict[str, Any] | None = None,
) -> AsyncGenerator[bytes, None]:
    """
    End‑to‑end RAG + LLM call for a given agent.
    """
    agent, domain = await _load_agent_and_domain(agent_id)

    documents = (extra_payload or {}).get("documents")
    if documents:
        logger.info(
            "RAG[request] agent_id=%s using in-memory documents count=%d",
            agent_id,
            len(documents),
        )
        context_chunks = retriever.retrieve_from_documents(
            query,
            documents=documents,
            k=10,
        )
    else:
        collection_name = (
            agent.get("rag_collection_override")
            or domain.get("rag_collection")
            or f"{domain['id']}_index"
        )
        logger.info(
            "RAG[request] agent_id=%s using collection=%s", agent_id, collection_name
        )
        context_chunks = retriever.retrieve(
            query,
            collection_name=collection_name,
            k=10,
        )

    logger.info(
        "RAG[context] agent_id=%s chunks=%d", agent_id, len(context_chunks)
    )

    messages = prompt_builder.build_prompt(
        query,
        context_chunks,
        agent_config=agent,
    )

    # Choose a model: allow agent override later, fallback to DEFAULT_LLM_MODEL.
    model_name = agent.get("model_name") or DEFAULT_LLM_MODEL

    payload: Dict[str, Any] = {"messages": messages, "model": model_name}
    if extra_payload:
        # Avoid sending raw documents to the provider payload
        cleaned_extra = {k: v for k, v in extra_payload.items() if k != "documents"}
        payload.update(cleaned_extra)

    status_code, headers, stream = await llm_service.llm_stream(payload)
    if status_code >= 400:
        logger.error(
            "RAG[llm] backend error status=%d agent_id=%s model=%s headers=%s",
            status_code,
            agent_id,
            model_name,
            headers,
        )
        raise HTTPException(status_code=status_code, detail="LLM backend error")

    async def iterator() -> AsyncGenerator[bytes, None]:
        async for chunk in stream:
            yield chunk

    return iterator()


