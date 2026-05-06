from sqlalchemy import String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class ProductMatch(Base):
    __tablename__ = 'product_matches'

    id:         Mapped[str]        = mapped_column(String(36), primary_key=True)
    email_id:   Mapped[str]        = mapped_column(ForeignKey('emails.id', ondelete='CASCADE'))
    sku:        Mapped[str]        = mapped_column(String(100))
    title:      Mapped[str | None] = mapped_column(String(500))
    score:      Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    email: Mapped['Email'] = relationship('Email', back_populates='product_matches')  # noqa: F821
