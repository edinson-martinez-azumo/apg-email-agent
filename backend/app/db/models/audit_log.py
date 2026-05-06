from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = 'audit_log'

    id:         Mapped[str]        = mapped_column(String(36), primary_key=True)
    email_id:   Mapped[str | None] = mapped_column(ForeignKey('emails.id', ondelete='SET NULL'))
    action:     Mapped[str]        = mapped_column(String(50))
    actor:      Mapped[str | None] = mapped_column(String(255))
    detail:     Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    email: Mapped['Email | None'] = relationship('Email', back_populates='audit_logs')  # noqa: F821
