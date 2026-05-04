# app\routers\chat_router.py
import uuid
import time
import json
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.schemas.responses_schema import ResponseRequest
from app.utils import build_prompt, build_messages, convert_to_openai_format, fully_serialize
from app.services.llm_service import LLMService
from app.redis_client import get_redis
from app.token_counter import count_tokens
from app.auth import get_api_key
import collections.abc


router = APIRouter()


async def stream_response(r, request_id):

    pubsub = r.pubsub()
    await pubsub.subscribe(f"stream:{request_id}")

    try:
        async for msg in pubsub.listen():

            if msg["type"] != "message":
                continue

            data = msg["data"]

            if isinstance(data, bytes):
                data = data.decode()

            if data == "[DONE]":
                yield "data: [DONE]\n\n"
                break

            yield data

            if data.startswith("event: response.usage"):
                break

    finally:
        await pubsub.unsubscribe(f"stream:{request_id}")
        await pubsub.close()


@router.post("/v1/responses")
async def create_response(
        req: ResponseRequest,
        user=Depends(get_api_key),
        r=Depends(get_redis)
):

    llm = LLMService(r)

    input_is_list = isinstance(req.input, list)

    tool_messages_present = (
        input_is_list and
        any(getattr(msg, "role", None) == "tool" for msg in req.input)
    )

    tools_present = req.tools is not None and len(req.tools) > 0

    print(f"DEBUG: tool_messages_present={tool_messages_present} tools_present={tools_present}")

    # =========================================================
    # ✅ STAGE 2 — tool results received
    # =========================================================
    if tool_messages_present:

        messages = build_messages(req)
        
        serializable_messages = fully_serialize(messages)
        print(f"DEBUG: STAGE 2-------\n{serializable_messages}")
        payload = {
            "model": req.model,
            "messages": serializable_messages,
            "tool_choice": "none",   # مهم
            "stream": False,
            "options": {
                "temperature": req.temperature,
                "top_p": req.top_p,
                "num_predict": req.max_output_tokens,
            },
        }
        result = await llm.tools_calling(payload)
        print(f"DEBUG RESULT:\n{result}")
        return convert_to_openai_format(result)


    # =========================================================
    # ✅ STAGE 1 — model should call tools
    # =========================================================
    if tools_present:

        messages = build_messages(req)
        
        serializable_messages = fully_serialize(messages)
        print(f"DEBUG: STAGE 1-------\n{serializable_messages}")
        payload = {
            "model": req.model,
            "messages": serializable_messages,
            "stream": False,
            "tools": req.tools,
            "tool_choice": req.tool_choice,
            "options": {
                "temperature": req.temperature,
                "top_p": req.top_p,
                "num_predict": req.max_output_tokens,
            },
        }

        result = await llm.tools_calling(payload)

        msg = result.get("message", {}) if isinstance(result, dict) else {}
        tool_calls = msg.get("tool_calls") or []

        openai_tool_calls = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            openai_tool_calls.append({
                "type": "function_call",
                "id": tc.get("id"),
                "call_id": tc.get("id"),
                "name": fn.get("name"),
                "arguments": json.dumps(fn.get("arguments", {})),
            })

        return JSONResponse({
            "id": f"resp_{uuid.uuid4().hex}",
            "object": "response",
            "created": int(time.time()),
            "model": req.model,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
            "output": openai_tool_calls,
        })


    # =========================================================
    # ✅ NORMAL TEXT GENERATION (non-stream)
    # =========================================================
    if not req.stream:

        prompt = build_prompt(req)
        input_tokens = count_tokens(prompt)

        payload = {
            "model": req.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": req.temperature,
                "top_p": req.top_p,
                "num_predict": req.max_output_tokens
            }
        }

        result = await llm.generate(payload)

        output = result.get("response", "") if isinstance(result, dict) else str(result)
        output_tokens = count_tokens(output)

        return JSONResponse({
            "id": f"resp_{uuid.uuid4().hex}",
            "object": "response",
            "created": int(time.time()),
            "model": req.model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            },
            "output": [{
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": output
                }]
            }]
        })


    # =========================================================
    # ✅ STREAM MODE (only normal text)
    # =========================================================
    request_id = uuid.uuid4().hex

    prompt = build_prompt(req)
    input_tokens = count_tokens(prompt)

    payload = {
        "model": req.model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": req.temperature,
            "top_p": req.top_p,
            "num_predict": req.max_output_tokens
        }
    }

    await llm.enqueue_stream(
        request_id,
        payload,
        user["user_id"],
        input_tokens
    )

    return StreamingResponse(
        stream_response(r, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
