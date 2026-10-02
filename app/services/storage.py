from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.models import Component, StorageBox, StorageCell
from app.services import BusinessRuleError


def _row_label(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def create_box(session: Session, *, name: str, rows: int, columns: int) -> StorageBox:
    name = name.strip()
    if not name:
        raise BusinessRuleError("收纳盒名称不能为空")
    if rows <= 0 or columns <= 0:
        raise BusinessRuleError("行数和列数必须大于 0")
    box = StorageBox(name=name, rows=rows, columns=columns)
    for row_index in range(rows):
        for column_index in range(columns):
            box.cells.append(StorageCell(
                row_index=row_index,
                column_index=column_index,
                label=f"{_row_label(row_index)}{column_index + 1}",
            ))
    session.add(box)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessRuleError("收纳盒名称已经存在") from exc
    return session.execute(
        select(StorageBox).options(selectinload(StorageBox.cells)).where(StorageBox.id == box.id)
    ).scalar_one()


def update_box(session: Session, box_id: int, *, name: str, rows: int, columns: int) -> StorageBox:
    box = session.execute(
        select(StorageBox).options(selectinload(StorageBox.cells)).where(StorageBox.id == box_id)
    ).scalar_one_or_none()
    if box is None:
        raise BusinessRuleError("收纳盒不存在")
    name = name.strip()
    if not name:
        raise BusinessRuleError("收纳盒名称不能为空")
    if rows <= 0 or columns <= 0:
        raise BusinessRuleError("行数和列数必须大于 0")

    removed = [cell for cell in box.cells if cell.row_index >= rows or cell.column_index >= columns]
    if any(cell.component_id is not None for cell in removed):
        raise BusinessRuleError("被裁掉的格位中还有元件，请先移动或清空")
    for cell in removed:
        box.cells.remove(cell)

    existing_positions = {(cell.row_index, cell.column_index) for cell in box.cells}
    for row_index in range(rows):
        for column_index in range(columns):
            if (row_index, column_index) not in existing_positions:
                box.cells.append(StorageCell(
                    row_index=row_index,
                    column_index=column_index,
                    label=f"{_row_label(row_index)}{column_index + 1}",
                ))
    box.name = name
    box.rows = rows
    box.columns = columns
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessRuleError("收纳盒名称或新格位标识已存在") from exc
    return session.execute(
        select(StorageBox).options(selectinload(StorageBox.cells)).where(StorageBox.id == box.id)
    ).scalar_one()


def assign_component(session: Session, component_id: int, cell_id: int) -> StorageCell:
    component = session.get(Component, component_id)
    cell = session.get(StorageCell, cell_id)
    if component is None:
        raise BusinessRuleError("元件不存在")
    if cell is None:
        raise BusinessRuleError("格位不存在")
    if cell.component_id is not None and cell.component_id != component_id:
        raise BusinessRuleError("目标格位已被占用")
    if component.storage_cell is not None and component.storage_cell.id != cell_id:
        component.storage_cell.component = None
    cell.component = component
    session.commit()
    session.refresh(cell)
    return cell


def update_cell(
    session: Session,
    cell_id: int,
    *,
    label: str,
    component_id: int | None,
) -> StorageCell:
    cell = session.get(StorageCell, cell_id)
    if cell is None:
        raise BusinessRuleError("格位不存在")
    label = label.strip()
    if not label:
        raise BusinessRuleError("格位标识不能为空")
    component = None
    if component_id is not None:
        component = session.get(Component, component_id)
        if component is None:
            raise BusinessRuleError("元件不存在")
        if component.storage_cell is not None and component.storage_cell.id != cell.id:
            component.storage_cell.component = None
    cell.label = label
    cell.component = component
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise BusinessRuleError("同一收纳盒内的格位标识不能重复") from exc
    session.refresh(cell)
    return cell


def delete_box(session: Session, box_id: int) -> None:
    box = session.execute(
        select(StorageBox).options(selectinload(StorageBox.cells)).where(StorageBox.id == box_id)
    ).scalar_one_or_none()
    if box is None:
        raise BusinessRuleError("收纳盒不存在")
    if any(cell.component_id is not None for cell in box.cells):
        raise BusinessRuleError("请先移走盒内元件")
    session.delete(box)
    session.commit()
