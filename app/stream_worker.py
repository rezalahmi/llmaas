# app/stream_worker.py (اصلاح شده)
import asyncio
import json
import httpx
import redis.asyncio as redis
import time
import uuid
from app.config import settings
from app.redis_client import get_redis
from app.token_counter import count_tokens 

import time
import json

def format_openai_chunk(request_id: str, model: str, content: str, finish_reason: str = None):
    """فرمت‌بندی داده‌ها مطابق با ساختار ChatCompletionChunk اپن‌ ای‌آی"""
    chunk = {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason
            }
        ]
    }
    return f"data: {json.dumps(chunk)}\n\n"



async def run():
    r = await get_redis()
    ollama_url = settings.OLLAMA_URL # از تنظیمات بخوانید

    while True:
        _, raw = await r.brpop("stream_queue")
        data = json.loads(raw)

        request_id = data["request_id"]
        payload = data["payload"]
        user_id = data["user_id"]
        input_tokens = data.get("input_tokens", 0) # خواندن ورودی توکن ها

        payload["stream"] = True # مطمئن شوید که stream فعال است

        all_output_content = ""
        output_tokens = 0
        is_first_chunk = True

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", ollama_url, json=payload) as resp:
                    resp.raise_for_status() # Raise HTTP errors

                    async for line in resp.aiter_lines():
                        if not line:
                            continue

                        ollama_data = json.loads(line)

                        response_text = ollama_data.get("response", "")
                        done = ollama_data.get("done", False)

                        if response_text:
                            all_output_content += response_text

                            await r.publish(
                                f"stream:{request_id}",
                                format_openai_chunk(
                                    request_id=request_id,
                                    model=payload["model"],
                                    content=response_text,
                                ),
                            )

                        if done:
                            await r.publish(
                                f"stream:{request_id}",
                                format_openai_chunk(
                                    request_id=request_id,
                                    model=payload["model"],
                                    content=None,
                                    finish_reason="stop",
                                ),
                            )
                            break



            # After loop finishes (either by done or break)
            if not all_output_content and input_tokens == 0: # Handle case where no output was generated and no input was provided
                # If it's not done, it means an error occurred or Ollama didn't respond as expected
                if not done:
                     await r.publish(f"stream:{request_id}", await format_openai_chunk({"delta": {"content": "Error: Ollama did not complete the stream."}, "finish_reason": "error"}))

            # Calculate output tokens at the end
            output_tokens = count_tokens(all_output_content)

            # Publish final message, maybe including usage (OpenAI doesn't usually send usage in stream chunks, but in a final response for non-stream)
            # For stream, usage is usually handled by logging separately or in a non-stream part of the API if needed.
            # If you want to mimic OpenAI's *final* chunk with finish_reason: "stop", you already did that with `if done:` block.

            # Publish [DONE] signal that your endpoint listens for
            await r.publish(f"stream:{request_id}", "data: [DONE]\n\n")


        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
            await r.publish(
                f"stream:{request_id}",
                format_openai_chunk(
                    request_id=request_id,
                    model=payload["model"],
                    content=f"Error: {e}",
                    finish_reason="error",
                ),
            )

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            await r.publish(
                f"stream:{request_id}",
                format_openai_chunk(
                    request_id=request_id,
                    model=payload["model"],
                    content=f"Error: {e}",
                    finish_reason="error",
                ),
            )


if __name__ == "__main__":
    # Ensure settings are loaded if needed, and redis client is initialized correctly
    # If app.config.settings needs async init, adjust accordingly.
    # For simplicity, assuming settings are loadable directly.
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Stream worker stopped.")
