import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.importers.bom import ParsedBom, parse_bom
from app.importers.normalizers import ImportValidationError
from app.routes.serializers import bom_dict
from app.schemas.boms import BomSubstitute
from app.schemas.imports import ImportConfirm
from app.services import BusinessRuleError
from app.services.bom import delete_bom, import_bom, pick_bom_item
from app.services.bom_matching import select_bom_item_candidate


router = APIRouter(prefix="/api/boms", tags=["boms"])


def _parsed_item_dict(item) -> dict[str, object]:
    return {
        "supplier_part": item.supplier_part,
        "comment": item.comment,
        "footprint": item.footprint,
        "secondary_category": item.secondary_category,
        "description": item.description,
        "quantity": item.quantity,
        "designators": item.designators,
        "warnings": item.warnings,
    }


@router.post("/preview")
async def preview_bom(request: Request, file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".xlsx":
        raise ImportValidationError("BOM 只支持 .xlsx 文件")
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as target:
            target.write(await file.read())
            path = Path(target.name)
        parsed = parse_bom(path)
    finally:
        if path is not None:
            path.unlink(missing_ok=True)

    token = uuid4().hex
    request.app.state.import_previews[token] = ("bom_pick", file.filename or "bom.xlsx", parsed)
    return {
        "token": token,
        "warnings": parsed.warnings,
        "items": [_parsed_item_dict(item) for item in parsed.items],
    }


@router.post("/confirm", status_code=status.HTTP_201_CREATED)
def confirm_bom_import(
    payload: ImportConfirm,
    request: Request,
    session: Session = Depends(get_db),
):
    preview = request.app.state.import_previews.get(payload.token)
    if preview is None or preview[0] != "bom_pick":
        raise BusinessRuleError("导入预览已失效，请重新选择文件")
    _, file_name, parsed = preview
    bom = import_bom(
        session,
        name=payload.name.strip() or Path(file_name).stem,
        file_name=file_name,
        parsed=parsed,
    )
    request.app.state.import_previews.pop(payload.token, None)
    return bom_dict(bom)


@router.post("/items/{item_id}/pick")
def pick_item(item_id: int, session: Session = Depends(get_db)):
    item = pick_bom_item(session, item_id)
    return {
        "id": item.id,
        "bom_id": item.bom_id,
        "picked": True,
        "bom_status": item.bom.status,
    }


@router.post("/items/{item_id}/substitute")
def substitute_item(
    item_id: int,
    payload: BomSubstitute,
    session: Session = Depends(get_db),
):
    item = select_bom_item_candidate(session, item_id, payload.component_id)
    return {
        "id": item.id,
        "bom_id": item.bom_id,
        "component_id": item.component_id,
        "original_supplier_part": item.supplier_part,
        "selected_supplier_part": item.component.supplier_part,
    }


@router.delete("/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bom(bom_id: int, session: Session = Depends(get_db)):
    delete_bom(session, bom_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
