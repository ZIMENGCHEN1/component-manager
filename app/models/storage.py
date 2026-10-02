from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class StorageBox(Base):
    __tablename__ = "storage_boxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    columns: Mapped[int] = mapped_column(Integer, nullable=False)

    cells: Mapped[list["StorageCell"]] = relationship(
        back_populates="box",
        cascade="all, delete-orphan",
        order_by="StorageCell.row_index, StorageCell.column_index",
    )


class StorageCell(Base):
    __tablename__ = "storage_cells"
    __table_args__ = (
        UniqueConstraint("box_id", "row_index", "column_index", name="uq_storage_cell_position"),
        UniqueConstraint("box_id", "label", name="uq_storage_cell_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    box_id: Mapped[int] = mapped_column(ForeignKey("storage_boxes.id"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("components.id"),
        unique=True,
        nullable=True,
    )

    box: Mapped[StorageBox] = relationship(back_populates="cells")
    component: Mapped["Component | None"] = relationship(back_populates="storage_cell")
