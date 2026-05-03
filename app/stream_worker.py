# app/stream_worker.py
import asyncio
import json
import httpx
import time
import uuid # برای تولید request_id

from app.redis_client import get_redis
from app.config import settings
from app.token_counter import count_tokens


# === توابع فرمت‌دهی برای Responses API ===

def format_response_created(request_id: str, model_name: str):
    """Generates the 'response.created' event."""
    return (
        "event: response.created\n"
        f"data: {json.dumps({'id': request_id, 'object': 'response', 'model': model_name})}\n\n"
    )

def format_response_delta(content: str):
    """Generates the 'response.output_text.delta' event."""
    return (
        "event: response.output_text.delta\n"
        f"data: {json.dumps({'delta': content})}\n\n"
    )

def format_response_completed():
    """Generates the 'response.completed' event."""
    return (
        "event: response.completed\n"
        "data: {}\n\n"
    )

def format_response_usage(total_tokens: dict):
    """Generates the 'response.usage' event (optional, but good practice)."""
    return (
        "event: response.usage\n"
        f"data:{json.dumps({"usage": total_tokens})}"
    )


async def run():
    r = await get_redis()
    
    # فرض می‌کنیم Ollama URL در تنظیمات موجود است
    ollama_url = settings.OLLAMA_URL 

    while True:
        # دریافت داده از صف Redis
        _, raw = await r.brpop("stream_queue")
        if not raw:
            continue

        data = json.loads(raw)
        
        request_id = data.get("request_id", str(uuid.uuid4())) # اگر request_id نبود، یکی بساز
        payload = data["payload"]
        model_name = payload.get("model", "default-model") # نام مدل را استخراج کن
        prompt_input = payload.get("input", "")
        prompt_tokens = count_tokens(prompt_input)
        # برای هدایت به URL درست Ollama
        ollama_api_endpoint = ollama_url

        # برای اینکه Ollama بداند باید stream کند
        payload["stream"] = True 

        # محاسبه توکن‌ها
        total_completion_tokens = 0
        completion_text = ""
        # اتصال به Ollama و دریافت stream
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                # ارسال event 'response.created' به کلاینت (از طریق Redis publish)
                await r.publish(f"stream:{request_id}", format_response_created(request_id, model_name))

                async with client.stream("POST", ollama_api_endpoint, json=payload) as resp:
                    resp.raise_for_status() # اگر خطایی در درخواست به Ollama بود، exception بدهد

                    async for line in resp.aiter_lines():
                        if not line:
                            continue

                        try:
                            ollama_chunk = json.loads(line)

                            
                            text_delta = ollama_chunk.get("response", "") # متنی که Ollama فرستاده
                            done = ollama_chunk.get("done", False)

                            if text_delta:
                                completion_text += text_delta
                                completion_tokens_in_chunk = len(text_delta.split()) # تخمین خیلی ساده!
                                total_completion_tokens += completion_tokens_in_chunk

                                # ارسال event 'response.output_text.delta'
                                await r.publish(f"stream:{request_id}", format_response_delta(text_delta))

                            if done:
                                # ارسال event 'response.usage' (اگر محاسبه شد)
                                completion_tokens = count_tokens(completion_text)
                                usage_payload = {
                                    "prompt_tokens": prompt_tokens,
                                    "completion_tokens": completion_tokens,
                                    "total_tokens": prompt_tokens + completion_tokens
                                    }
                                await r.publish(f"stream:{request_id}", format_response_usage(usage_payload))
                                
                                # ارسال event 'response.completed'
                                await r.publish(f"stream:{request_id}", format_response_completed())

                                break # خروج از حلقه دریافت chunk از Ollama

                        except json.JSONDecodeError:
                            print(f"Skipping non-JSON line from Ollama: {line}")
                        except Exception as e:
                            print(f"Error processing Ollama chunk: {e}")
                            # در صورت بروز خطا در پردازش chunk، یک خطای کامل بفرست
                            await r.publish(f"stream:{request_id}", f"event: error\ndata: {json.dumps({'message': f'Error processing chunk: {e}'})}\n\n")
                            break # خروج در صورت خطا

            except httpx.HTTPStatusError as e:
                print(f"HTTP error occurred: {e}")
                # ارسال خطای HTTP به کلاینت
                await r.publish(f"stream:{request_id}", f"event: error\ndata: {json.dumps({'message': f'HTTP error from Ollama: {e}'})}\n\n")
            except httpx.RequestError as e:
                print(f"An error occurred while requesting {e.request.url!r}.")
                # ارسال خطای درخواست به کلاینت
                await r.publish(f"stream:{request_id}", f"event: error\ndata: {json.dumps({'message': f'Request error to Ollama: {e}'})}\n\n")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                # ارسال خطای کلی به کلاینت
                await r.publish(f"stream:{request_id}", f"event: error\ndata: {json.dumps({'message': f'Unexpected error: {e}'})}\n\n")
        

# برای اجرای این فایل به صورت مستقیم
if __name__ == "__main__":
    print("Starting stream worker...")
    asyncio.run(run())
