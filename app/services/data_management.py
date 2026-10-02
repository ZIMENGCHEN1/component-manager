from contextlib import closing
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, selectinload

from app.models import Bom, Component, Order, StockMovement, StorageBox, StorageCell
from app.services import BusinessRuleError


REQUIRED_TABLES = {
    "components",
    "storage_boxes",
    "storage_cells",
    "orders",
    "order_items",
    "boms",
    "bom_items",
    "stock_movements",
}


def _database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        raise BusinessRuleError("备份与恢复只支持文件型 SQLite 数据库")
    return Path(url.database).resolve()


def _add_sheet(workbook: Workbook, title: str, headers: list[str], rows) -> None:
    sheet = workbook.create_sheet(title)
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    for column in sheet.columns:
        values = [str(cell.value) for cell in column if cell.value is not None]
        width = min(max((len(value) for value in values), default=8) + 2, 42)
        sheet.column_dimensions[column[0].column_letter].width = width


def build_excel_export(session: Session) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)

    components = session.execute(
        select(Component)
        .options(selectinload(Component.storage_cell).selectinload(StorageCell.box))
        .order_by(Component.id)
    ).scalars().all()
    _add_sheet(
        workbook,
        "元件库",
        [
            "供应商", "Supplier Part", "参数", "封装", "二级分类", "Description",
            "制造商", "制造商型号", "可用库存", "收纳盒", "格位",
        ],
        (
            (
                component.supplier or "",
                component.supplier_part or "",
                component.comment,
                component.footprint,
                component.secondary_category,
                component.description,
                component.manufacturer,
                component.manufacturer_part,
                component.available_quantity,
                component.storage_cell.box.name if component.storage_cell else "",
                component.storage_cell.label if component.storage_cell else "",
            )
            for component in components
        ),
    )

    boxes = session.execute(
        select(StorageBox)
        .options(selectinload(StorageBox.cells).selectinload(StorageCell.component))
        .order_by(StorageBox.id)
    ).scalars().all()
    _add_sheet(
        workbook,
        "收纳盒",
        ["收纳盒", "行", "列", "格位", "Supplier Part", "参数", "库存"],
        (
            (
                box.name,
                cell.row_index + 1,
                cell.column_index + 1,
                cell.label,
                cell.component.supplier_part or "" if cell.component else "",
                cell.component.comment if cell.component else "",
                cell.component.available_quantity if cell.component else "",
            )
            for box in boxes
            for cell in box.cells
        ),
    )

    movements = session.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.component))
        .order_by(StockMovement.id)
    ).scalars().all()
    _add_sheet(
        workbook,
        "库存流水",
        ["时间", "Supplier Part", "参数", "数量变化", "类型", "来源类型", "来源 ID", "备注"],
        (
            (
                movement.created_at,
                movement.component.supplier_part or "",
                movement.component.comment,
                movement.quantity_delta,
                movement.movement_type,
                movement.source_type,
                movement.source_id,
                movement.note,
            )
            for movement in movements
        ),
    )

    orders = session.execute(
        select(Order).options(selectinload(Order.items)).order_by(Order.id)
    ).scalars().all()
    _add_sheet(
        workbook,
        "订单",
        ["订单号", "订单日期", "导入时间", "Supplier Part", "厂家", "厂家型号", "订购数量", "发货数量", "状态"],
        (
            (
                order.order_number,
                order.order_date,
                order.imported_at,
                item.supplier_part,
                item.manufacturer,
                item.manufacturer_part,
                item.ordered_quantity,
                item.shipped_quantity,
                item.status,
            )
            for order in orders
            for item in order.items
        ),
    )

    boms = session.execute(
        select(Bom).options(selectinload(Bom.items)).order_by(Bom.id)
    ).scalars().all()
    _add_sheet(
        workbook,
        "BOM",
        [
            "BOM 名称", "状态", "导入时间", "Supplier Part", "参数", "封装",
            "二级分类", "Description", "数量", "Designator", "提示",
        ],
        (
            (
                bom.name,
                bom.status,
                bom.imported_at,
                item.supplier_part,
                item.comment,
                item.footprint,
                item.secondary_category,
                item.description,
                item.quantity,
                item.designators,
                item.warning,
            )
            for bom in boms
            for item in bom.items
        ),
    )

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def validate_database(path: Path) -> None:
    try:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BusinessRuleError("数据库完整性检查未通过")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
    except (sqlite3.DatabaseError, OSError) as exc:
        raise BusinessRuleError("上传文件不是有效的 SQLite 数据库") from exc
    missing = REQUIRED_TABLES - tables
    if missing:
        raise BusinessRuleError("备份文件不是本系统的完整数据库")


def create_database_backup(database_url: str) -> bytes:
    database_path = _database_path(database_url)
    if not database_path.exists():
        raise BusinessRuleError("当前数据库文件不存在")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as target_file:
            temporary_path = Path(target_file.name)
        with closing(sqlite3.connect(str(database_path))) as source, closing(sqlite3.connect(str(temporary_path))) as target:
            source.backup(target)
        return temporary_path.read_bytes()
    except (sqlite3.DatabaseError, OSError) as exc:
        raise BusinessRuleError("数据库备份失败") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def restore_database(database_url: str, uploaded_path: Path, backup_directory: Path) -> Path:
    validate_database(uploaded_path)
    database_path = _database_path(database_url)
    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safety_backup = backup_directory / f"before-restore-{timestamp}.db"
    safety_backup.write_bytes(create_database_backup(database_url))

    try:
        with closing(sqlite3.connect(str(uploaded_path))) as source, closing(sqlite3.connect(str(database_path))) as target:
            source.backup(target)
        validate_database(database_path)
    except Exception as exc:
        with closing(sqlite3.connect(str(safety_backup))) as source, closing(sqlite3.connect(str(database_path))) as target:
            source.backup(target)
        if isinstance(exc, BusinessRuleError):
            raise
        raise BusinessRuleError("数据库恢复失败，已保留原数据") from exc
    return safety_backup
