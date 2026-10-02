from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import xlrd

from app.importers.normalizers import (
    ImportValidationError,
    normalize_supplier_part,
    normalize_text,
    parse_money,
    parse_non_negative_int,
)


@dataclass(frozen=True)
class ParsedOrderItem:
    supplier_part: str
    manufacturer: str
    manufacturer_part: str
    order_package: str
    product_name: str
    ordered_quantity: int
    shipped_quantity: int
    unit_price: Decimal | None
    amount: Decimal | None


@dataclass(frozen=True)
class ParsedOrder:
    order_number: str
    order_date: datetime | None
    items: list[ParsedOrderItem]


REQUIRED_HEADERS = {"商品编号", "订购数量（修改后）", "发货数量"}


def _label_value(sheet: xlrd.sheet.Sheet, label: str) -> str:
    for row_index in range(sheet.nrows):
        values = sheet.row_values(row_index)
        for column, value in enumerate(values):
            if normalize_text(value).rstrip("：:") == label and column + 1 < len(values):
                return normalize_text(values[column + 1])
    return ""


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for format_string in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, format_string)
        except ValueError:
            continue
    return None


def parse_lcsc_order(path: str | Path) -> ParsedOrder:
    try:
        workbook = xlrd.open_workbook(str(path), on_demand=True)
    except Exception as exc:
        raise ImportValidationError(f"无法读取订单文件：{exc}") from exc

    try:
        target_sheet = None
        header_index = -1
        columns: dict[str, int] = {}
        for sheet in workbook.sheets():
            for row_index in range(sheet.nrows):
                mapping = {
                    normalize_text(value): column
                    for column, value in enumerate(sheet.row_values(row_index))
                    if normalize_text(value)
                }
                if REQUIRED_HEADERS.issubset(mapping):
                    target_sheet = sheet
                    header_index = row_index
                    columns = mapping
                    break
            if target_sheet is not None:
                break

        if target_sheet is None:
            raise ImportValidationError("订单中未找到商品明细表头")

        order_number = _label_value(target_sheet, "订单编号")
        if not order_number:
            raise ImportValidationError("订单中未找到订单编号")
        order_date = _parse_date(_label_value(target_sheet, "下单日期"))
        items: list[ParsedOrderItem] = []

        for excel_row in range(header_index + 1, target_sheet.nrows):
            values = target_sheet.row_values(excel_row)
            supplier_part = normalize_supplier_part(values[columns["商品编号"]] if len(values) > columns["商品编号"] else None)
            if not supplier_part:
                continue

            def value_for(name: str) -> object:
                column = columns.get(name)
                return values[column] if column is not None and len(values) > column else None

            items.append(ParsedOrderItem(
                supplier_part=supplier_part,
                manufacturer=normalize_text(value_for("品牌")),
                manufacturer_part=normalize_text(value_for("厂家型号")),
                order_package=normalize_text(value_for("封装")),
                product_name=normalize_text(value_for("商品名称")),
                ordered_quantity=parse_non_negative_int(value_for("订购数量（修改后）"), f"第 {excel_row + 1} 行订购数量"),
                shipped_quantity=parse_non_negative_int(value_for("发货数量"), f"第 {excel_row + 1} 行发货数量"),
                unit_price=parse_money(value_for("商品单价")),
                amount=parse_money(value_for("商品金额")),
            ))

        if not items:
            raise ImportValidationError("订单中没有可导入的商品")
        return ParsedOrder(order_number=order_number, order_date=order_date, items=items)
    finally:
        workbook.release_resources()
