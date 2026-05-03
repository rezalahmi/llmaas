# app/services/llm_service.py
import json
from app.tasks import generate_task
class LLMService:

    def __init__(self, redis):
        self.redis = redis

    async def enqueue_stream(self, request_id, payload, user_id, input_tokens):
        await self.redis.lpush("stream_queue", json.dumps({
            "request_id": request_id,
            "payload": payload,
            "user_id": user_id,
            "input_tokens": input_tokens
        }))

        
    async def generate(self, payload):
        """
        Non-stream mode – synchronous request handled by Celery.
        """
        result = generate_task.delay(payload)
        return result.get(timeout=300)