from fastapi import APIRouter
from app.llm.tool_loop import run_tool_loop

router = APIRouter()

@router.post("/v1/chat/completions")
async def chat_completion(req: dict):

    model = req["model"]
    messages = req["messages"]
    tools = req.get("tools", [])

    response = await run_tool_loop(
        model=model,
        messages=messages,
        tools=tools
    )

    return response
