from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    order_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    component_id: Mapped[int | None] = mapped_column(ForeignKey("components.id"), nullable=True)
    supplier_part: Mapped[str] = mapped_column(String(80), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    manufacturer_part: Mapped[str] = mapped_column(String(160), default="")
    order_package: Mapped[str] = mapped_column(String(255), default="")
    product_name: Mapped[str] = mapped_column(String(500), default="")
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    shipped_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    stocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order: Mapped[Order] = relationship(back_populates="items")
    component: Mapped["Component | None"] = relationship(back_populates="order_items")
