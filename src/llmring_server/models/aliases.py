from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Alias(BaseModel):
    id: Optional[int] = None
    project_id: str
    profile: str = "default"
    alias: str
    model: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AliasRequest(BaseModel):
    profile: str = "default"
    model: str
    metadata: Optional[Dict[str, Any]] = None


class BindRequest(BaseModel):
    alias: str
    profile: str = "default"
    model: str
    metadata: Optional[Dict[str, Any]] = None
