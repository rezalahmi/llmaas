# app\schemas\admin.py
from pydantic import BaseModel


class KeyActiveUpdate(BaseModel):
    is_active: bool

class KeyCreate(BaseModel):
    user_id: int
    user: str
    quota: int