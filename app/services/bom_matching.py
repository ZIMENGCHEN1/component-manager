import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Bom, BomItem, Component, StockMovement, StorageCell
from app.services import BusinessRuleError


def normalize_comment_for_match(value: object) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("μ", "u").replace("µ", "u")
    return re.sub(r"\s+", " ", text)


def required_quantity_for_candidate(
    items: list[BomItem],
    picked_item_ids: set[int],
    item: BomItem,
    candidate_id: int,
) -> int:
    return sum(
        value.quantity
        for value in items
        if value.id not in picked_item_ids
        and (value.id == item.id or value.component_id == candidate_id)
    )


def find_exact_component(session: Session, supplier_part: str) -> Component | None:
    return session.execute(
        select(Component)
        .options(selectinload(Component.storage_cell).selectinload(StorageCell.box))
        .where(
            Component.supplier == "LCSC",
            Component.supplier_part == supplier_part,
        )
    ).scalar_one_or_none()


def find_comment_candidates(session: Session, item: BomItem) -> list[Component]:
    key = normalize_comment_for_match(item.comment)
    if not key:
        return []
    exact = find_exact_component(session, item.supplier_part)
    if exact is not None and exact.available_quantity >= item.quantity:
        return []

    components = session.execute(
        select(Component)
        .options(selectinload(Component.storage_cell).selectinload(StorageCell.box))
        .order_by(Component.id)
    ).scalars().all()
    candidates = [
        component
        for component in components
        if component.id != (exact.id if exact else None)
        and normalize_comment_for_match(component.comment) == key
    ]
    return sorted(
        candidates,
        key=lambda component: (
            component.available_quantity < item.quantity,
            -component.available_quantity,
            component.supplier_part or "",
        ),
    )


def select_bom_item_candidate(session: Session, item_id: int, component_id: int) -> BomItem:
    item = session.execute(
        select(BomItem)
        .options(
            selectinload(BomItem.bom).selectinload(Bom.items),
            selectinload(BomItem.component),
        )
        .where(BomItem.id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise BusinessRuleError("BOM 行不存在")
    candidate = session.execute(
        select(Component)
        .options(selectinload(Component.storage_cell))
        .where(Component.id == component_id)
    ).scalar_one_or_none()
    if candidate is None:
        raise BusinessRuleError("候选元件不存在")
    if item.bom.status == "picked":
        raise BusinessRuleError("该 BOM 已经完成领料")
    picked_item_ids = set(session.execute(
        select(StockMovement.source_id).where(
            StockMovement.source_type == "bom_item",
            StockMovement.source_id.in_([value.id for value in item.bom.items]),
        )
    ).scalars())
    if item.id in picked_item_ids:
        raise BusinessRuleError("该 BOM 行已经领料")

    exact = find_exact_component(session, item.supplier_part)
    if exact is not None and exact.available_quantity >= item.quantity:
        raise BusinessRuleError("精确匹配元件库存充足，无需替代")
    item_comment = normalize_comment_for_match(item.comment)
    if not item_comment or normalize_comment_for_match(candidate.comment) != item_comment:
        raise BusinessRuleError("候选元件 Comment 与 BOM 不匹配")
    if exact is not None and candidate.id == exact.id:
        raise BusinessRuleError("库存不足的精确元件不能作为替代候选")
    required_quantity = required_quantity_for_candidate(
        item.bom.items,
        picked_item_ids,
        item,
        candidate.id,
    )
    if candidate.available_quantity < required_quantity:
        raise BusinessRuleError(
            f"候选元件库存不足：合计需要 {required_quantity} 件，"
            f"可用 {candidate.available_quantity} 件"
        )

    try:
        item.component = candidate
        session.commit()
    except Exception:
        session.rollback()
        raise
    return item
