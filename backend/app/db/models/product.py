from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db.base_class import Base


class Product(Base):
    __tablename__ = 'product_embeddings_v2'

    sku:           Mapped[str]         = mapped_column(String(100), primary_key=True)
    title:         Mapped[str | None]  = mapped_column(String(500))
    search_text:   Mapped[str | None]  = mapped_column(Text)
    type:          Mapped[str | None]  = mapped_column(Text)
    materials:     Mapped[str | None]  = mapped_column(Text)
    moq:           Mapped[str | None]  = mapped_column(Text)
    capacities:    Mapped[str | None]  = mapped_column(Text)
    price_base:    Mapped[str | None]  = mapped_column(Text)
    price_10k:     Mapped[str | None]  = mapped_column(Text)
    price_25k:     Mapped[str | None]  = mapped_column(Text)
    price_50k:     Mapped[str | None]  = mapped_column(Text)
    price_100k:    Mapped[str | None]  = mapped_column(Text)
    in_stock:      Mapped[bool | None] = mapped_column(Boolean, server_default='false')
    image_url:     Mapped[str | None]  = mapped_column(Text)
    dimensions:    Mapped[str | None]  = mapped_column(Text)
    updated_at:    Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
