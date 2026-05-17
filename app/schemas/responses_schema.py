from pydantic import BaseModel
from typing import Optional, List, Union, Dict, Any, Literal


class InputText(BaseModel):
    type: str = "input_text"
    text: str

class ToolMessage(BaseModel):
    role: Literal["tool"]
    tool_name: str
    tool_call_id: str
    content: str

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: List[InputText]

class AssistantToolCall(BaseModel):
    type: str
    id: str
    function: Dict[str, Any]


class AssistantMessage(BaseModel):
    role: Literal["assistant"]
    tool_calls: List[AssistantToolCall]

InputItem = Union[ChatMessage, ToolMessage, AssistantMessage]





class ResponseRequest(BaseModel):
    model: str
    input: Union[str, List[InputItem]]


    stream: Optional[bool] = False

    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    max_output_tokens: Optional[int] = 512

    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = "auto"

    instructions: Optional[str] = None
