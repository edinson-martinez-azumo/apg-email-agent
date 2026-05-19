from pydantic import BaseModel
from datetime import datetime


class DashboardStats(BaseModel):
    total_emails: int
    pending: int
    reviewed: int
    drafts_sent: int
    avg_response_time_hours: float | None


class RecentSentEmail(BaseModel):
    id: str
    from_email: str
    from_name: str | None
    subject: str | None
    sent_at: datetime | None

    model_config = {'from_attributes': True}


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_sent: list[RecentSentEmail]
