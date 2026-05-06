from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db.base_class import Base


class ProductEmbedding(Base):
    __tablename__ = 'product_embeddings'

    sku:        Mapped[str]        = mapped_column(String(100), primary_key=True)
    title:      Mapped[str | None] = mapped_column(String(500))
    search_text: Mapped[str | None] = mapped_column(Text)
    embedding:  Mapped[list[float]] = mapped_column(Vector(384))
    updated_at: Mapped[DateTime]   = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
