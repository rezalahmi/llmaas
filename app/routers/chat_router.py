# from fastapi import APIRouter
# from app.llm.tool_loop import run_tool_loop
# from fastapi import APIRouter, Depends
# from fastapi.responses import JSONResponse
# from app.schemas.request import ResponseRequest
# from app.utils import build_prompt
# from app.services.llm_service import LLMService
# from app.token_counter import count_tokens
# from app.auth import get_api_key


# router = APIRouter()

# @router.post("/v1/chat/completions")
# async def chat_completion(req: dict):

#     model = req["model"]
#     messages = req["messages"]
#     tools = req.get("tools", [])

#     response = await run_tool_loop(
#         model=model,
#         messages=messages,
#         tools=tools
#     )

#     return response


# @router.post("/v1/responses")
# async def responses(req: ResponseRequest, user=Depends(get_api_key)):
#     prompt = build_prompt(req)
#     input_tokens = count_tokens(prompt)

#     payload = {
#         "model": req.model,
#         "prompt": prompt,
#         "options": {
#             "temperature": req.temperature,
#             "top_p": req.top_p,
#             "num_predict": req.max_output_tokens,
#         }
#     }

#     # non-stream
#     llm = LLMService()
#     output = await llm.generate(payload)

#     output_tokens = count_tokens(output)

#     return JSONResponse({
#         "id": f"resp_{uuid.uuid4().hex}",
#         "object": "response",
#         "created": int(time.time()),
#         "model": req.model,
#         "usage": {
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "total_tokens": input_tokens + output_tokens
#         },
#         "output": [{
#             "type": "message",
#             "role": "assistant",
#             "content": [{
#                 "type": "output_text",
#                 "text": output
#             }]
#         }]
#     })
import uuid
import time
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.schemas.responses_schema import ResponseRequest
from app.utils import build_prompt
from app.services.llm_service import LLMService
from app.redis_client import get_redis
from app.token_counter import count_tokens
from app.auth import get_api_key

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

    finally:
        await pubsub.unsubscribe(f"stream:{request_id}")


@router.post("/v1/responses")
async def create_response(
        req: ResponseRequest,
        user=Depends(get_api_key),
        r=Depends(get_redis)
):

    prompt = build_prompt(req)
    input_tokens = count_tokens(prompt)

    payload = {
        "model": req.model,
        "prompt": prompt,
        "stream": req.stream,
        "options": {
            "temperature": req.temperature,
            "top_p": req.top_p,
            "num_predict": req.max_output_tokens
        }
    }

    # STREAM
    if req.stream:

        request_id = uuid.uuid4().hex

        service = LLMService(r)

        await service.enqueue_stream(
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

    # NON STREAM

    llm = LLMService(r)

    result = await llm.generate(payload)
    if not isinstance(result, dict):
        output = str(result)
    else:
        output = result.get("response", "")
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
