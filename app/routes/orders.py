import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.importers.normalizers import ImportValidationError
from app.importers.order import parse_lcsc_order
from app.routes.serializers import order_dict, order_item_dict
from app.schemas.imports import ImportConfirm
from app.schemas.storage import CellAssignment
from app.services import BusinessRuleError
from app.services.orders import (
    assign_order_item_to_cell,
    import_order,
    link_order_item,
)


router = APIRouter(prefix="/api/orders", tags=["orders"])


def _parsed_item_dict(item) -> dict[str, object]:
    return {
        "supplier_part": item.supplier_part,
        "manufacturer": item.manufacturer,
        "manufacturer_part": item.manufacturer_part,
        "order_package": item.order_package,
        "product_name": item.product_name,
        "ordered_quantity": item.ordered_quantity,
        "shipped_quantity": item.shipped_quantity,
    }


@router.post("/preview")
async def preview_order(request: Request, file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".xls":
        raise ImportValidationError("立创订单只支持 .xls 文件")
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as target:
            target.write(await file.read())
            path = Path(target.name)
        parsed = parse_lcsc_order(path)
    finally:
        if path is not None:
            path.unlink(missing_ok=True)

    token = uuid4().hex
    request.app.state.import_previews[token] = ("order", file.filename or "order.xls", parsed)
    return {
        "token": token,
        "order_number": parsed.order_number,
        "items": [_parsed_item_dict(item) for item in parsed.items],
    }


@router.post("/confirm", status_code=status.HTTP_201_CREATED)
def confirm_order_import(
    payload: ImportConfirm,
    request: Request,
    session: Session = Depends(get_db),
):
    preview = request.app.state.import_previews.get(payload.token)
    if preview is None or preview[0] != "order":
        raise BusinessRuleError("导入预览已失效，请重新选择文件")
    _, file_name, parsed = preview
    order = import_order(session, file_name=file_name, parsed=parsed)
    request.app.state.import_previews.pop(payload.token, None)
    return order_dict(order)


@router.post("/items/{item_id}/place")
def place_order_item(item_id: int, payload: CellAssignment, session: Session = Depends(get_db)):
    if payload.cell_id is None:
        raise BusinessRuleError("请选择格位")
    return order_item_dict(assign_order_item_to_cell(session, item_id, payload.cell_id))


@router.post("/items/{item_id}/link")
def link_unmatched_item(item_id: int, payload: CellAssignment, session: Session = Depends(get_db)):
    if payload.component_id is None:
        raise BusinessRuleError("请选择元件")
    return order_item_dict(link_order_item(session, item_id, payload.component_id))
