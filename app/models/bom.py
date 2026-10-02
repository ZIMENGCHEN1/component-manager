from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Bom(Base):
    __tablename__ = "boms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    picked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["BomItem"]] = relationship(
        back_populates="bom",
        cascade="all, delete-orphan",
    )


class BomItem(Base):
    __tablename__ = "bom_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(ForeignKey("boms.id"), nullable=False)
    component_id: Mapped[int | None] = mapped_column(ForeignKey("components.id"), nullable=True)
    supplier_part: Mapped[str] = mapped_column(String(80), nullable=False)
    comment: Mapped[str] = mapped_column(String(255), default="")
    footprint: Mapped[str] = mapped_column(String(255), default="")
    secondary_category: Mapped[str] = mapped_column(
        String(160),
        default="",
        server_default="",
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    designators: Mapped[str] = mapped_column(Text, default="")
    warning: Mapped[str] = mapped_column(Text, default="")

    bom: Mapped[Bom] = relationship(back_populates="items")
    component: Mapped["Component | None"] = relationship(back_populates="bom_items")
