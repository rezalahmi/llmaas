# app/utils.py

def build_prompt(body: dict) -> str:
    prompt_parts = []

    # system instructions (Responses API)
    if body.get("instructions"):
        prompt_parts.append(f"System: {body['instructions']}")

    # input (Responses API)
    if isinstance(body.get("input"), str):
        prompt_parts.append(f"User: {body['input']}")

    elif isinstance(body.get("input"), list):
        for item in body["input"]:
            if item.get("type") == "input_text":
                text = item.get("text", "")
                if text:
                    prompt_parts.append(f"User: {text}")

    # messages (Chat Completions API)
    if isinstance(body.get("messages"), list):
        for msg in body["messages"]:
            role = msg.get("role")
            content = msg.get("content", "")

            if not content:
                continue

            if role == "system":
                prompt_parts.append(f"System: {content}")

            elif role == "user":
                prompt_parts.append(f"User: {content}")

            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

            else:
                prompt_parts.append(content)

    # آخر پرامپت برای تولید پاسخ
    prompt_parts.append("Assistant:")

    return "\n".join(prompt_parts)
