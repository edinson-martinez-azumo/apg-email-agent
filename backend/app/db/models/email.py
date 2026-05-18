from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class Email(Base):
    __tablename__ = 'emails'

    id:           Mapped[str]        = mapped_column(String(36), primary_key=True)
    gmail_id:     Mapped[str]        = mapped_column(String(255), unique=True)
    thread_id:    Mapped[str | None] = mapped_column(String(255), index=True)
    from_email:   Mapped[str]        = mapped_column(String(255))
    from_name:    Mapped[str | None] = mapped_column(String(255))
    subject:      Mapped[str | None] = mapped_column(String(500))
    body_text:    Mapped[str | None] = mapped_column(Text)
    received_at:  Mapped[DateTime]   = mapped_column(DateTime(timezone=True))
    status:       Mapped[str]        = mapped_column(String(50), default='pending')
    created_at:   Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Email reference headers for proper threading
    message_id:   Mapped[str | None] = mapped_column(String(500), index=True)
    in_reply_to:  Mapped[str | None] = mapped_column(String(500))
    references:   Mapped[str | None] = mapped_column(Text)

    draft:           Mapped['Draft']              = relationship('Draft', back_populates='email', uselist=False)  # noqa: F821
    product_matches: Mapped[list['ProductMatch']] = relationship('ProductMatch', back_populates='email')          # noqa: F821
    audit_logs:      Mapped[list['AuditLog']]     = relationship('AuditLog', back_populates='email')             # noqa: F821
