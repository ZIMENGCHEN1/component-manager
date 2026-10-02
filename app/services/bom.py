from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.importers.bom import ParsedBom
from app.models import Bom, BomItem, Component, StockMovement
from app.services import BusinessRuleError
from app.services.inventory import apply_stock_change


@dataclass
class BomPickGroup:
    component: Component
    items: list[BomItem]
    picked_item_ids: set[int]

    @property
    def pending_items(self) -> list[BomItem]:
        return [value for value in self.items if value.id not in self.picked_item_ids]

    @property
    def display_items(self) -> list[BomItem]:
        return self.pending_items or self.items

    @property
    def pending_quantity(self) -> int:
        return sum(value.quantity for value in self.pending_items)

    @property
    def total_quantity(self) -> int:
        return sum(value.quantity for value in self.items)


def build_pick_groups(
    items: list[BomItem],
    picked_item_ids: set[int],
) -> dict[int, BomPickGroup]:
    groups: dict[int, BomPickGroup] = {}
    for item in items:
        if item.component is None or item.component.storage_cell is None:
            continue
        cell_id = item.component.storage_cell.id
        group = groups.get(cell_id)
        if group is None:
            group = BomPickGroup(
                component=item.component,
                items=[],
                picked_item_ids=picked_item_ids,
            )
            groups[cell_id] = group
        group.items.append(item)
    return groups


def _load_bom(session: Session, bom_id: int) -> Bom | None:
    return session.execute(
        select(Bom)
        .options(
            selectinload(Bom.items)
            .selectinload(BomItem.component)
            .selectinload(Component.storage_cell)
        )
        .where(Bom.id == bom_id)
    ).scalar_one_or_none()


def import_bom(session: Session, *, name: str, file_name: str, parsed: ParsedBom) -> Bom:
    bom = Bom(name=name.strip() or file_name, file_name=file_name)
    session.add(bom)
    try:
        for parsed_item in parsed.items:
            component = session.execute(
                select(Component).where(
                    Component.supplier == "LCSC",
                    Component.supplier_part == parsed_item.supplier_part,
                )
            ).scalar_one_or_none()

            warnings = list(parsed_item.warnings)
            if component is not None and component.comment and component.comment != parsed_item.comment:
                warnings.append("Comment 与元件库记录不一致")
            if component is not None and component.footprint and component.footprint != parsed_item.footprint:
                warnings.append("Footprint 与元件库记录不一致")

            bom.items.append(BomItem(
                component=component,
                supplier_part=parsed_item.supplier_part,
                comment=parsed_item.comment,
                footprint=parsed_item.footprint,
                secondary_category=parsed_item.secondary_category,
                description=parsed_item.description,
                quantity=parsed_item.quantity,
                designators=", ".join(parsed_item.designators),
                warning="；".join(warnings),
            ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_bom(session, bom.id)


def pick_bom_item(session: Session, item_id: int) -> BomItem:
    item = session.execute(
        select(BomItem)
        .options(
            selectinload(BomItem.component).selectinload(Component.storage_cell),
            selectinload(BomItem.bom).selectinload(Bom.items),
        )
        .where(BomItem.id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise BusinessRuleError("BOM 行不存在")
    if item.bom.status == "picked":
        raise BusinessRuleError("该 BOM 已经完成领料")

    picked_ids = set(session.execute(
        select(StockMovement.source_id).where(
            StockMovement.source_type == "bom_item",
            StockMovement.source_id.in_([value.id for value in item.bom.items]),
        )
    ).scalars())
    if item.id in picked_ids:
        raise BusinessRuleError("该格元件已经领取")
    if item.component is None:
        raise BusinessRuleError("该元件未建档")
    if item.component.storage_cell is None:
        raise BusinessRuleError("该元件还未分配格位")
    pending_items = [
        value
        for value in item.bom.items
        if value.id not in picked_ids and value.component_id == item.component_id
    ]
    required_quantity = sum(value.quantity for value in pending_items)
    if item.component.available_quantity < required_quantity:
        raise BusinessRuleError(
            f"库存不足：合计需要 {required_quantity} 件，"
            f"可用 {item.component.available_quantity} 件"
        )

    try:
        for pending_item in pending_items:
            apply_stock_change(
                session,
                item.component,
                -pending_item.quantity,
                "bom_item_out",
                source_type="bom_item",
                source_id=pending_item.id,
                note=f"BOM 聚合领料：{item.bom.name}",
            )
        picked_ids.update(value.id for value in pending_items)
        if picked_ids == {value.id for value in item.bom.items}:
            item.bom.status = "picked"
            item.bom.picked_at = datetime.now()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return item


def delete_bom(session: Session, bom_id: int) -> None:
    bom = session.execute(
        select(Bom).options(selectinload(Bom.items)).where(Bom.id == bom_id)
    ).scalar_one_or_none()
    if bom is None:
        raise BusinessRuleError("BOM 不存在")
    item_ids = [item.id for item in bom.items]
    has_item_movements = bool(item_ids) and session.execute(
        select(StockMovement.id).where(
            StockMovement.source_type == "bom_item",
            StockMovement.source_id.in_(item_ids),
        ).limit(1)
    ).scalar_one_or_none() is not None
    has_legacy_movements = session.execute(
        select(StockMovement.id).where(
            StockMovement.source_type == "bom",
            StockMovement.source_id == bom.id,
        ).limit(1)
    ).scalar_one_or_none() is not None
    if bom.status == "picked" or has_item_movements or has_legacy_movements:
        raise BusinessRuleError("已发生领料的 BOM 不能删除")
    session.delete(bom)
    session.commit()
