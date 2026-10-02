from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.importers.order import ParsedOrder
from app.models import Component, Order, OrderItem, StorageCell
from app.services import BusinessRuleError
from app.services.inventory import apply_stock_change


def _load_order(session: Session, order_id: int) -> Order | None:
    return session.execute(
        select(Order)
        .options(
            selectinload(Order.items)
            .selectinload(OrderItem.component)
            .selectinload(Component.storage_cell)
        )
        .where(Order.id == order_id)
    ).scalar_one_or_none()


def import_order(session: Session, *, file_name: str, parsed: ParsedOrder) -> Order:
    duplicate = session.execute(
        select(Order.id).where(Order.order_number == parsed.order_number)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise BusinessRuleError("该订单已经导入")

    order = Order(
        order_number=parsed.order_number,
        order_date=parsed.order_date,
        file_name=file_name,
    )
    session.add(order)
    try:
        session.flush()
        for parsed_item in parsed.items:
            component = session.execute(
                select(Component)
                .options(selectinload(Component.storage_cell))
                .where(
                    Component.supplier == "LCSC",
                    Component.supplier_part == parsed_item.supplier_part,
                )
            ).scalar_one_or_none()

            if component is None:
                status = "unmatched"
            elif component.storage_cell is None:
                status = "pending_location"
            else:
                status = "stocked"
                if not component.manufacturer and parsed_item.manufacturer:
                    component.manufacturer = parsed_item.manufacturer
                if not component.manufacturer_part and parsed_item.manufacturer_part:
                    component.manufacturer_part = parsed_item.manufacturer_part

            order_item = OrderItem(
                order=order,
                component=component,
                supplier_part=parsed_item.supplier_part,
                manufacturer=parsed_item.manufacturer,
                manufacturer_part=parsed_item.manufacturer_part,
                order_package=parsed_item.order_package,
                product_name=parsed_item.product_name,
                ordered_quantity=parsed_item.ordered_quantity,
                shipped_quantity=parsed_item.shipped_quantity,
                unit_price=parsed_item.unit_price,
                amount=parsed_item.amount,
                status=status,
            )
            session.add(order_item)
            session.flush()

            if status == "stocked":
                apply_stock_change(
                    session,
                    component,
                    parsed_item.shipped_quantity,
                    "order_in",
                    source_type="order_item",
                    source_id=order_item.id,
                    note=f"订单入库：{parsed.order_number}",
                )
                order_item.stocked_at = datetime.now()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_order(session, order.id)


def assign_order_item_to_cell(session: Session, item_id: int, cell_id: int) -> OrderItem:
    item = session.execute(
        select(OrderItem)
        .options(
            selectinload(OrderItem.component).selectinload(Component.storage_cell),
            selectinload(OrderItem.order),
        )
        .where(OrderItem.id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise BusinessRuleError("订单项不存在")
    if item.status == "stocked":
        raise BusinessRuleError("该订单项已经入库")
    if item.status != "pending_location" or item.component is None:
        raise BusinessRuleError("该订单项还未匹配元件")

    cell = session.get(StorageCell, cell_id)
    if cell is None:
        raise BusinessRuleError("格位不存在")
    if cell.component_id is not None and cell.component_id != item.component_id:
        raise BusinessRuleError("目标格位已被占用")

    try:
        if item.component.storage_cell is not None and item.component.storage_cell.id != cell_id:
            item.component.storage_cell.component = None
        cell.component = item.component
        apply_stock_change(
            session,
            item.component,
            item.shipped_quantity,
            "order_in",
            source_type="order_item",
            source_id=item.id,
            note=f"订单入库：{item.order.order_number}",
        )
        item.status = "stocked"
        item.stocked_at = datetime.now()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return item


def link_order_item(session: Session, item_id: int, component_id: int) -> OrderItem:
    item = session.execute(
        select(OrderItem)
        .options(
            selectinload(OrderItem.order),
            selectinload(OrderItem.component),
        )
        .where(OrderItem.id == item_id)
    ).scalar_one_or_none()
    component = session.execute(
        select(Component)
        .options(selectinload(Component.storage_cell))
        .where(Component.id == component_id)
    ).scalar_one_or_none()
    if item is None:
        raise BusinessRuleError("订单项不存在")
    if item.status != "unmatched":
        raise BusinessRuleError("只能处理未匹配的订单项")
    if component is None:
        raise BusinessRuleError("元件不存在")

    try:
        item.component = component
        if component.storage_cell is None:
            item.status = "pending_location"
        else:
            apply_stock_change(
                session,
                component,
                item.shipped_quantity,
                "order_in",
                source_type="order_item",
                source_id=item.id,
                note=f"订单入库：{item.order.order_number}",
            )
            item.status = "stocked"
            item.stocked_at = datetime.now()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return item
