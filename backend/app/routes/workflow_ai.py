from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import GROQ_MODEL_WORKFLOW
from app.services.llm import ensure_llm_configured, llm_stream

router = APIRouter()


@router.post("/api/workflow-ai")
async def workflow_ai(request: Request):
    ensure_llm_configured()
    body = await request.json()
    sop_text = body.get("sop_text", "")
    action = body.get("action")
    current_step = body.get("current_step")
    step_context = body.get("step_context")

    if action == "parse":
        system_prompt = (
            "You are a workflow parser. Given a Standard Operating Procedure (SOP) written in natural language, "
            "break it into discrete executable steps. Return ONLY valid JSON array of steps, no markdown.\n\n"
            "Each step should have:\n"
            '- "step_number": integer\n'
            '- "title": short title (5-8 words)\n'
            '- "description": detailed instructions for this step\n'
            '- "action_type": one of "review", "analyze", "verify", "input", "decision", "communicate", "document", "calculate"\n'
            '- "ai_can_assist": boolean - whether AI can help with this step\n'
            '- "estimated_minutes": integer estimate\n\n'
            'Example output:\n[{"step_number":1,"title":"Gather client information","description":"Collect the insured\'s name, address, policy number, and coverage details from the submission documents.","action_type":"input","ai_can_assist":true,"estimated_minutes":5}]'
        )
        user_prompt = f"Parse this SOP into steps:\n\n{sop_text}"
    elif action == "assist":
        system_prompt = (
            "You are an insurance operations AI assistant. The user is executing a workflow step-by-step. "
            "For the current step, provide detailed guidance, suggestions, and any relevant analysis. "
            "Be specific and actionable. Format your response with markdown."
        )
        user_prompt = (
            f"Workflow context:\n{sop_text}\n\n"
            f"Current Step {current_step.get('step_number') if current_step else ''}: {current_step.get('title') if current_step else ''}\n"
            f"Description: {current_step.get('description') if current_step else ''}\n\n"
            f"Additional context from previous steps:\n{step_context or 'None yet'}\n\n"
            "Provide detailed guidance for completing this step."
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'parse' or 'assist'.")

    status, headers, stream = await llm_stream(
        {
            "model": GROQ_MODEL_WORKFLOW,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
        }
    )
    return StreamingResponse(stream, status_code=status, headers=headers)
