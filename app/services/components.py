from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.importers.normalizers import normalize_supplier_part, normalize_text
from app.models import Component
from app.services import BusinessRuleError


EDITABLE_FIELDS = {
    "supplier",
    "supplier_part",
    "comment",
    "footprint",
    "manufacturer",
    "manufacturer_part",
    "secondary_category",
    "description",
}


def create_component(
    session: Session,
    *,
    comment: str,
    footprint: str,
    supplier: str | None = None,
    supplier_part: str | None = None,
    manufacturer: str = "",
    manufacturer_part: str = "",
    secondary_category: str = "",
    description: str = "",
) -> Component:
    normalized_part = normalize_supplier_part(supplier_part) or None
    component = Component(
        supplier=normalize_text(supplier) or ("LCSC" if normalized_part else None),
        supplier_part=normalized_part,
        comment=normalize_text(comment),
        footprint=normalize_text(footprint),
        manufacturer=normalize_text(manufacturer),
        manufacturer_part=normalize_text(manufacturer_part),
        secondary_category=normalize_text(secondary_category),
        description=normalize_text(description),
    )
    session.add(component)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessRuleError("该供应商编号已经存在") from exc
    session.refresh(component)
    return component


def update_component(session: Session, component_id: int, **changes: object) -> Component:
    component = session.get(Component, component_id)
    if component is None:
        raise BusinessRuleError("元件不存在")
    for field, value in changes.items():
        if field not in EDITABLE_FIELDS:
            continue
        if field == "supplier_part":
            value = normalize_supplier_part(value) or None
        else:
            value = normalize_text(value) or (None if field == "supplier" else "")
        setattr(component, field, value)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessRuleError("该供应商编号已经存在") from exc
    session.refresh(component)
    return component


def delete_component(session: Session, component_id: int) -> None:
    component = session.get(Component, component_id)
    if component is None:
        raise BusinessRuleError("元件不存在")
    if component.available_quantity != 0:
        raise BusinessRuleError("有库存的元件不能删除")
    if component.storage_cell is not None:
        component.storage_cell.component = None
    session.delete(component)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessRuleError("该元件已被 BOM 或订单引用，不能删除") from exc
