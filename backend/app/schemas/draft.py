from pydantic import BaseModel
from datetime import datetime


class DraftRead(BaseModel):
    id: str
    email_id: str
    body: str
    edited_body: str | None
    approved_by: str | None
    approved_at: datetime | None
    sent_at: datetime | None
    gmail_draft_id: str | None
    created_at: datetime

    model_config = {'from_attributes': True}


class DraftUpdate(BaseModel):
    edited_body: str
