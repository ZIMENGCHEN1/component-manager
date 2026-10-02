from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Component, StockMovement
from app.services import BusinessRuleError


def apply_stock_change(
    session: Session,
    component: Component,
    delta: int,
    movement_type: str,
    *,
    source_type: str = "",
    source_id: int | None = None,
    note: str = "",
) -> StockMovement:
    new_quantity = component.available_quantity + delta
    if new_quantity < 0:
        raise BusinessRuleError("库存不足，不能完成该操作")
    component.available_quantity = new_quantity
    movement = StockMovement(
        component=component,
        quantity_delta=delta,
        movement_type=movement_type,
        source_type=source_type,
        source_id=source_id,
        note=note.strip(),
    )
    session.add(movement)
    session.flush()
    return movement


def adjust_stock(session: Session, component_id: int, delta: int, *, note: str = "") -> StockMovement:
    if delta == 0:
        raise BusinessRuleError("调整数量不能为 0")
    component = session.get(Component, component_id)
    if component is None:
        raise BusinessRuleError("元件不存在")
    try:
        movement = apply_stock_change(
            session,
            component,
            delta,
            "adjustment",
            note=note,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(movement)
    return movement


def reverse_stock_movement(session: Session, movement_id: int) -> StockMovement:
    original = session.get(StockMovement, movement_id)
    if original is None:
        raise BusinessRuleError("库存流水不存在")
    if original.movement_type != "adjustment":
        raise BusinessRuleError("目前只允许撤销手动调整流水")
    reversed_movement_id = session.scalar(
        select(StockMovement.id).where(
            StockMovement.source_type == "stock_movement",
            StockMovement.source_id == original.id,
            StockMovement.movement_type == "adjustment_reversal",
        )
    )
    if reversed_movement_id is not None:
        raise BusinessRuleError("该库存流水已经撤销")

    component = session.get(Component, original.component_id)
    if component is None:
        raise BusinessRuleError("元件不存在")
    try:
        reversal = apply_stock_change(
            session,
            component,
            -original.quantity_delta,
            "adjustment_reversal",
            source_type="stock_movement",
            source_id=original.id,
            note=f"撤销流水 #{original.id}：{original.note}".rstrip("："),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(reversal)
    return reversal
