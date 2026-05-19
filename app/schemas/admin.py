# app\schemas\admin.py
from pydantic import BaseModel


class KeyCreate(BaseModel):
    user_id: int
    user: str
    quota: int