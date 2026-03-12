from typing import Any, AsyncGenerator

import httpx
from fastapi import HTTPException

from app.core.config import GROQ_API_KEY, GROQ_OPENAI_COMPAT_URL


def ensure_llm_configured() -> None:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured")


async def llm_stream(payload: dict[str, Any]) -> tuple[int, dict[str, str], AsyncGenerator[bytes, None]]:
    client = httpx.AsyncClient(timeout=None)
    req = client.build_request(
        "POST",
        GROQ_OPENAI_COMPAT_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    resp = await client.send(req, stream=True)

    if resp.status_code >= 400:
        body = await resp.aread()
        await resp.aclose()
        await client.aclose()
        text = body.decode("utf-8", errors="ignore")
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
        if resp.status_code == 402:
            raise HTTPException(status_code=402, detail="Payment required. Please add credits to your workspace.")
        raise HTTPException(status_code=500, detail=f"AI gateway error: {text}")

    async def iterator() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return 200, {"Content-Type": "text/event-stream"}, iterator()
