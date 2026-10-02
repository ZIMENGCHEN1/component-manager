from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.bom import ParsedBom
from app.models import Component
from app.services import BusinessRuleError


METADATA_FIELDS = ("secondary_category", "description")


@dataclass(frozen=True)
class BomLibraryImportResult:
    created_count: int
    reused_count: int
    warnings: list[str]


@dataclass(frozen=True)
class BomLibraryConflict:
    supplier_part: str
    field: str
    current_value: str
    incoming_value: str


def find_bom_library_conflicts(
    session: Session,
    parsed: ParsedBom,
) -> list[BomLibraryConflict]:
    parts = [item.supplier_part for item in parsed.items]
    components = session.execute(
        select(Component).where(
            Component.supplier == "LCSC",
            Component.supplier_part.in_(parts),
        )
    ).scalars().all()
    by_part = {value.supplier_part: value for value in components}
    conflicts = []
    for item in parsed.items:
        component = by_part.get(item.supplier_part)
        if component is None:
            continue
        for field in METADATA_FIELDS:
            current = getattr(component, field)
            incoming = getattr(item, field)
            if current and incoming and current != incoming:
                conflicts.append(BomLibraryConflict(
                    supplier_part=item.supplier_part,
                    field=field,
                    current_value=current,
                    incoming_value=incoming,
                ))
    return conflicts


def import_bom_library(
    session: Session,
    *,
    parsed: ParsedBom,
    overwrite_fields: dict[str, set[str]] | None = None,
) -> BomLibraryImportResult:
    created_count = 0
    reused_count = 0
    warnings = list(parsed.warnings)
    overwrite_fields = overwrite_fields or {}
    conflicts = find_bom_library_conflicts(session, parsed)
    valid_pairs = {(value.supplier_part, value.field) for value in conflicts}
    requested_pairs = {
        (supplier_part, field)
        for supplier_part, fields in overwrite_fields.items()
        for field in fields
    }
    if not requested_pairs <= valid_pairs:
        raise BusinessRuleError("覆盖选择无效，请重新预览 BOM")
    try:
        for item in parsed.items:
            component = session.execute(
                select(Component).where(
                    Component.supplier == "LCSC",
                    Component.supplier_part == item.supplier_part,
                )
            ).scalar_one_or_none()
            if component is None:
                session.add(Component(
                    supplier="LCSC",
                    supplier_part=item.supplier_part,
                    comment=item.comment,
                    footprint=item.footprint,
                    manufacturer=item.manufacturer,
                    manufacturer_part=item.manufacturer_part,
                    secondary_category=item.secondary_category,
                    description=item.description,
                ))
                created_count += 1
                continue

            reused_count += 1
            if component.comment and component.comment != item.comment:
                warnings.append(f"{item.supplier_part} 的 Comment 与元件库记录不一致")
            if component.footprint and component.footprint != item.footprint:
                warnings.append(f"{item.supplier_part} 的 Footprint 与元件库记录不一致")
            for field in METADATA_FIELDS:
                current = getattr(component, field)
                incoming = getattr(item, field)
                if not current and incoming:
                    setattr(component, field, incoming)
                elif (item.supplier_part, field) in requested_pairs:
                    setattr(component, field, incoming)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return BomLibraryImportResult(
        created_count=created_count,
        reused_count=reused_count,
        warnings=warnings,
    )
