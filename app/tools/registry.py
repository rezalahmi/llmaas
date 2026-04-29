# app\tools\registry.py
from typing import Callable, Dict

class ToolRegistry:

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, dict] = {}

    def register(self, name: str, schema: dict, handler: Callable):
        self.tools[name] = handler
        self.schemas[name] = schema

    def get(self, name: str):
        return self.tools.get(name)

    def get_schema(self, name: str):
        return self.schemas.get(name)


registry = ToolRegistry()
