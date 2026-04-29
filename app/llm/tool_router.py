# app\llm\tool_router.py
from app.tools.registry import registry


def classify_tool_calls(tool_calls):

    server_calls = []
    client_calls = []

    for call in tool_calls:

        name = call["function"]["name"]

        if registry.get(name):
            server_calls.append(call)
        else:
            client_calls.append(call)

    return server_calls, client_calls
