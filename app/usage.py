# app\usage.py
import json
import time

async def log_usage(r, user_id, model, input_tokens, output_tokens):
    total = input_tokens + output_tokens

    record = {
        "user_id": user_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "timestamp": int(time.time())
    }

    await r.incrby(f"usage:{user_id}", total)
    await r.lpush("usage_log", json.dumps(record))