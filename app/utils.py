# app\utils.py
def build_prompt(body):
    prompt = ""

    if body.get("instructions"):
        prompt += body["instructions"] + "\n\n"

    if isinstance(body.get("input"), str):
        prompt += body["input"]

    elif isinstance(body.get("input"), list):
        for item in body["input"]:
            if item.get("type") == "input_text":
                prompt += item["text"] + "\n"

    return prompt


