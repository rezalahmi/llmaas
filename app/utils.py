# app\utils.py
from app.schemas.responses_schema import ResponseRequest
from typing import Any
import uuid
import time
import json

def fully_serialize(obj):
    if hasattr(obj, "dict") and callable(obj.dict):
        return {k: fully_serialize(v) for k, v in obj.dict().items()}
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return {k: fully_serialize(v) for k, v in obj.model_dump().items()}
    if isinstance(obj, dict):
        return {k: fully_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [fully_serialize(v) for v in obj]
    return obj


def build_prompt(req: ResponseRequest) -> str:
    prompt_parts = []

    # System Instructions
    if req.instructions:
        prompt_parts.append(f"System: {req.instructions}")

    # input handling
    if isinstance(req.input, str):
        prompt_parts.append(f"User: {req.input}")

    elif isinstance(req.input, list):
        for item in req.input:
            role = item.role.capitalize()

            for content in item.content:

                if content.type in ["text", "input_text"]:
                    prompt_parts.append(f"{role}: {content.text}")

    # End marker
    prompt_parts.append("Assistant:")

    return "\n".join(prompt_parts)




def build_messages(req: ResponseRequest) -> list[dict]:
    messages: list[dict] = []

    # system instructions
    if req.instructions:
        messages.append({
            "role": "system",
            "content": req.instructions
        })

    # input: string
    if isinstance(req.input, str):
        messages.append({
            "role": "user",
            "content": req.input
        })
        return messages

    # input: list[InputItem]
    for item in req.input:
        if item.role == "tool":
            messages.append({
                "role": "tool",
                "tool_name": item.tool_name,
                "tool_call_id": item.tool_call_id,
                "content": item.content
            })
        elif item.role == "assistant" and item.tool_calls:
            messages.append({
                "role": "assistant",
                "tool_calls": item.tool_calls
            })
        else:
            text = "\n".join([c.text for c in item.content])
            messages.append({"role": item.role, "content": text})

    return messages



def has_tool_messages(input_data) -> bool:
    if not isinstance(input_data, list):
        return False

    for msg in input_data:
        if isinstance(msg, dict) and msg.get("role") == "tool":
            return True

    return False




def _to_json_serializable(obj: Any) -> Any:
    # primitives
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # dict
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}

    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [_to_json_serializable(v) for v in obj]

    # Pydantic v1 models
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass

    # Pydantic v2 models
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass

    # Fallback
    return str(obj)

def to_json_serializable(obj: Any) -> Any:
    return _to_json_serializable(obj)



from typing import Any
def deep_to_dict(obj: Any):
    # پایدانتیک مدل
    if hasattr(obj, "dict"):
        return {k: deep_to_dict(v) for k, v in obj.dict().items()}
    if hasattr(obj, "model_dump"):
        return {k: deep_to_dict(v) for k, v in obj.model_dump().items()}
    # dict
    if isinstance(obj, dict):
        return {k: deep_to_dict(v) for k, v in obj.items()}
    # لیست/تاپل
    if isinstance(obj, (list, tuple)):
        return [deep_to_dict(v) for v in obj]
    # else
    return obj




def convert_to_openai_format(result: dict) -> dict:
    """
    Converts Ollama response to OpenAI-style JSON used by client.
    """

    response = {
        "id": f"resp_{uuid.uuid4().hex}",
        "object": "response",
        "created": result.get("created_at"),
        "model": result.get("model"),
        "usage": {
            "input_tokens": result.get("prompt_eval_count", 0),
            "output_tokens": result.get("eval_count", 0),
            "total_tokens": (
                (result.get("prompt_eval_count") or 0)
                + (result.get("eval_count") or 0)
            ),
        },
        "output": [],
    }

    msg = result.get("message")
    if msg:
        # حالت پاسخ کامل مدل
        response["output"].append({
            "type": "message",
            "role": msg.get("role", "assistant"),
            "content": msg.get("content"),
            "thinking": msg.get("thinking"),
        })
        return response

    # اگر پاسخ فقط tool_calls داشت (Stage 1)
    tool_calls = (
        result.get("message", {}).get("tool_calls")
        or result.get("tool_calls")
        or []
    )
    for tc in tool_calls:
        response["output"].append({
            "type": "function_call",
            "id": tc.get("id"),
            "call_id": tc.get("id"),
            "name": tc.get("function", {}).get("name"),
            "arguments": json.dumps(tc.get("function", {}).get("arguments", {})),
        })

    return response

