from pydantic import BaseModel
from typing import Optional, List, Union, Dict, Any


class InputText(BaseModel):
    type: str = "input_text"
    text: str


class InputItem(BaseModel):
    role: Optional[str] = "user"
    content: List[InputText]


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
