# app\llm\tool_loop.py
from app.llm.ollama_client import generate
from app.llm.tool_router import classify_tool_calls
from app.tools.executor import execute_server_tool


async def run_tool_loop(model, messages, tools):

    while True:

        response = await generate(
            model=model,
            messages=messages,
            tools=tools
        )

        msg = response["choices"][0]["message"]

        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            return response

        server_calls, client_calls = classify_tool_calls(tool_calls)

        # اجرای server tools
        for call in server_calls:

            result = await execute_server_tool(call)

            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": str(result)
            })

        # اگر client tool وجود داشت
        if client_calls:
            return response
