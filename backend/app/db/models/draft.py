from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class Draft(Base):
    __tablename__ = 'drafts'

    id:             Mapped[str]            = mapped_column(String(36), primary_key=True)
    email_id:       Mapped[str]            = mapped_column(ForeignKey('emails.id', ondelete='CASCADE'))
    body:           Mapped[str]            = mapped_column(Text)
    edited_body:    Mapped[str | None]     = mapped_column(Text)
    approved_by:    Mapped[str | None]     = mapped_column(String(255))
    approved_at:    Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    sent_at:        Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    gmail_draft_id: Mapped[str | None]     = mapped_column(String(255))
    created_at:     Mapped[DateTime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    email: Mapped['Email'] = relationship('Email', back_populates='draft')  # noqa: F821
