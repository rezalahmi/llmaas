# app/schemas/quota.py

from pydantic import BaseModel, Field
from typing import Optional


class CreditQuotaRequest(BaseModel):
    amount: int = Field(..., gt=0)
    reason: Optional[str] = None
    reference_id: Optional[str] = None
    days_to_add: Optional[int] = 30 


class DebitQuotaRequest(BaseModel):
    amount: int = Field(..., gt=0)
    reason: Optional[str] = None
    reference_id: Optional[str] = None
