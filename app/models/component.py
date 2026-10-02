from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Component(Base):
    __tablename__ = "components"
    __table_args__ = (
        UniqueConstraint("supplier", "supplier_part", name="uq_component_supplier_part"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_part: Mapped[str | None] = mapped_column(String(80), nullable=True)
    comment: Mapped[str] = mapped_column(String(255), default="")
    footprint: Mapped[str] = mapped_column(String(255), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    manufacturer_part: Mapped[str] = mapped_column(String(160), default="")
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
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    storage_cell: Mapped["StorageCell | None"] = relationship(back_populates="component", uselist=False)
    bom_items: Mapped[list["BomItem"]] = relationship(back_populates="component")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="component")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="component",
        cascade="all, delete-orphan",
    )
