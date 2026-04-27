# app\main.py
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import uuid, time, json

from app.auth import get_api_key
from app.rate_limit import check_rate_limit
from app.token_counter import count_tokens
from app.usage import log_usage
from app.tasks import generate_task
from app.utils import build_prompt
from app.config import DEFAULT_MODEL
from app.redis_client import init_redis, close_redis, get_redis
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_redis()

@app.on_event("shutdown")
async def shutdown():
    await close_redis()

@app.get("/health")
async def health():
    return {"status": "ok"}


async def stream_response(request_id, user_id, input_tokens):
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"stream:{request_id}")

    full_text = ""

    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue

        data = msg["data"]

        if data == "[DONE]":
            output_tokens = count_tokens(full_text)

            await log_usage(
                r,
                user_id,
                DEFAULT_MODEL,
                input_tokens,
                output_tokens
            )

            yield "data: [DONE]\n\n"
            break

        parsed = json.loads(data)
        token = parsed.get("response", "")
        full_text += token

        yield f"data: {json.dumps({'delta': token})}\n\n"


@app.post("/v1/responses")
async def responses(req: Request, user=Depends(get_api_key)):
    body = await req.json()

    prompt = build_prompt(body)
    input_tokens = count_tokens(prompt)

    r = await get_redis()

    await check_rate_limit(
        r,
        user["user_id"],
        user.get("rpm_limit", 60)
    )

    payload = {
        "model": DEFAULT_MODEL,
        "prompt": prompt,
        "options": {
            "temperature": body.get("temperature", 0.7),
            "top_p": body.get("top_p", 0.9),
            "num_predict": body.get("max_output_tokens", 512),
        }
    }

    if body.get("stream"):
        request_id = uuid.uuid4().hex

        await r.lpush("stream_queue", json.dumps({
            "request_id": request_id,
            "payload": payload,
            "user_id": user["user_id"],
            "input_tokens": input_tokens
        }))

        return StreamingResponse(
            stream_response(request_id, user["user_id"], input_tokens),
            media_type="text/event-stream"
        )

    task = generate_task.delay(payload)
    result = task.get(timeout=300)

    output = result.get("response", "")
    output_tokens = count_tokens(output)

    await log_usage(
        r,
        user["user_id"],
        DEFAULT_MODEL,
        input_tokens,
        output_tokens
    )

    return JSONResponse({
        "id": f"resp_{uuid.uuid4().hex}",
        "object": "response",
        "created": int(time.time()),
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        },
        "output": [{
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": output
            }]
        }]
    })
