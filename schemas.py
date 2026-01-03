# schemas.py
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None  # For multi-user support later

class ChatResponse(BaseModel):
    response: str
    payload_preview: Optional[Dict[str, Any]] = None
    current_step: str
    completed: bool = False
    po_number: Optional[str] = None
    session_id: str