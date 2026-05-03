# app\utils.py
from app.schemas.responses_schema import ResponseRequest


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
                if content.type == "input_text":
                    prompt_parts.append(f"{role}: {content.text}")

    # End marker
    prompt_parts.append("Assistant:")
    return "\n".join(prompt_parts)
