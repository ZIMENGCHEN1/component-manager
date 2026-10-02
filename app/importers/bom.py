from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from app.importers.normalizers import (
    ImportValidationError,
    normalize_supplier_part,
    normalize_text,
    parse_non_negative_int,
    split_designators,
)


@dataclass
class ParsedBomItem:
    supplier_part: str
    comment: str
    footprint: str
    quantity: int
    designators: list[str]
    secondary_category: str = ""
    description: str = ""
    manufacturer: str = ""
    manufacturer_part: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedBom:
    items: list[ParsedBomItem]
    warnings: list[str] = field(default_factory=list)


REQUIRED_COLUMNS = {"Supplier Part", "Comment", "Footprint", "Quantity"}


def _find_header(rows: list[tuple[object, ...]]) -> tuple[int, dict[str, int]]:
    for index, row in enumerate(rows[:20]):
        mapping = {normalize_text(value): column for column, value in enumerate(row) if normalize_text(value)}
        if REQUIRED_COLUMNS.issubset(mapping):
            return index, mapping
    missing = ", ".join(sorted(REQUIRED_COLUMNS))
    raise ImportValidationError(f"缺少必要列：{missing}")


def parse_bom(path: str | Path) -> ParsedBom:
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ImportValidationError(f"无法读取 BOM 文件：{exc}") from exc

    try:
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        header_index, columns = _find_header(rows)
        merged: dict[str, ParsedBomItem] = {}
        warnings: list[str] = []

        for excel_row, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            supplier_part = normalize_supplier_part(row[columns["Supplier Part"]] if len(row) > columns["Supplier Part"] else None)
            if not supplier_part:
                if any(normalize_text(value) for value in row):
                    raise ImportValidationError(f"第 {excel_row} 行缺少 Supplier Part")
                continue
            quantity = parse_non_negative_int(
                row[columns["Quantity"]] if len(row) > columns["Quantity"] else None,
                f"第 {excel_row} 行 Quantity",
            )
            if quantity == 0:
                raise ImportValidationError(f"第 {excel_row} 行 Quantity 必须大于 0")
            comment = normalize_text(row[columns["Comment"]] if len(row) > columns["Comment"] else None)
            footprint = normalize_text(row[columns["Footprint"]] if len(row) > columns["Footprint"] else None)
            designators = split_designators(row[columns["Designator"]]) if "Designator" in columns and len(row) > columns["Designator"] else []
            manufacturer = normalize_text(row[columns["Manufacturer"]]) if "Manufacturer" in columns and len(row) > columns["Manufacturer"] else ""
            manufacturer_part = normalize_text(row[columns["Manufacturer Part"]]) if "Manufacturer Part" in columns and len(row) > columns["Manufacturer Part"] else ""
            secondary_category = normalize_text(row[columns["Secondary Category"]]) if "Secondary Category" in columns and len(row) > columns["Secondary Category"] else ""
            description = normalize_text(row[columns["Description"]]) if "Description" in columns and len(row) > columns["Description"] else ""

            existing = merged.get(supplier_part)
            if existing:
                if existing.comment != comment or existing.footprint != footprint:
                    message = f"{supplier_part} 在 BOM 中出现不同的 Comment 或 Footprint"
                    existing.warnings.append(message)
                    warnings.append(message)
                existing.quantity += quantity
                existing.designators.extend(value for value in designators if value not in existing.designators)
                for field_name, label, incoming in (
                    ("secondary_category", "Secondary Category", secondary_category),
                    ("description", "Description", description),
                ):
                    current = getattr(existing, field_name)
                    if not current and incoming:
                        setattr(existing, field_name, incoming)
                    elif current and incoming and current != incoming:
                        message = f"{supplier_part} 在 BOM 中出现不同的 {label}"
                        existing.warnings.append(message)
                        warnings.append(message)
            else:
                merged[supplier_part] = ParsedBomItem(
                    supplier_part=supplier_part,
                    comment=comment,
                    footprint=footprint,
                    quantity=quantity,
                    designators=designators,
                    secondary_category=secondary_category,
                    description=description,
                    manufacturer=manufacturer,
                    manufacturer_part=manufacturer_part,
                )

        if not merged:
            raise ImportValidationError("BOM 中没有可导入的元件")
        return ParsedBom(items=list(merged.values()), warnings=warnings)
    finally:
        workbook.close()


__all__ = ["ImportValidationError", "ParsedBom", "ParsedBomItem", "parse_bom"]
