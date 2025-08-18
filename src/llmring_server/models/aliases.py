from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class Alias(BaseModel):
    id: Optional[int] = None
    project_id: str
    alias: str
    model: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AliasRequest(BaseModel):
    model: str
    metadata: Optional[Dict[str, Any]] = None


class BindRequest(BaseModel):
    alias: str
    model: str
    metadata: Optional[Dict[str, Any]] = None


