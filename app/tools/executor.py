# app\tools\executor.py
import json
from app.tools.registry import registry


async def execute_server_tool(call):

    name = call["function"]["name"]

    args = json.loads(call["function"]["arguments"])

    handler = registry.get(name)

    if not handler:
        raise Exception(f"Tool {name} not found")

    result = await handler(**args)

    return result
