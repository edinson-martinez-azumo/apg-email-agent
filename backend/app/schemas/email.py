from pydantic import BaseModel
from datetime import datetime


class ThreadEmailRead(BaseModel):
    id: str
    gmail_id: str
    from_email: str
    from_name: str | None
    subject: str | None
    body_text: str | None
    received_at: datetime

    model_config = {'from_attributes': True}


class EmailRead(BaseModel):
    id: str
    gmail_id: str
    thread_id: str | None
    from_email: str
    from_name: str | None
    subject: str | None
    body_text: str | None
    received_at: datetime
    status: str
    created_at: datetime
    thread: list[ThreadEmailRead] = []

    model_config = {'from_attributes': True}


class EmailListResponse(BaseModel):
    items: list[EmailRead]
    total: int
    page: int
    size: int
