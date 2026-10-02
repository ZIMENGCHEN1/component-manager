import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.importers.bom import parse_bom
from app.importers.normalizers import ImportValidationError
from app.schemas.imports import BomLibraryConfirm
from app.services import BusinessRuleError
from app.services.bom_library import find_bom_library_conflicts, import_bom_library


router = APIRouter(prefix="/api/bom-library", tags=["bom-library"])


def _item_dict(item) -> dict[str, object]:
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
async def preview_bom_library(
    request: Request,
    file: UploadFile,
    session: Session = Depends(get_db),
):
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
    request.app.state.import_previews[token] = (
        "bom_library",
        file.filename or "bom.xlsx",
        parsed,
    )
    return {
        "token": token,
        "warnings": parsed.warnings,
        "items": [_item_dict(item) for item in parsed.items],
        "conflicts": [
            {
                "supplier_part": value.supplier_part,
                "field": value.field,
                "current_value": value.current_value,
                "incoming_value": value.incoming_value,
            }
            for value in find_bom_library_conflicts(session, parsed)
        ],
    }


@router.post("/confirm", status_code=status.HTTP_201_CREATED)
def confirm_bom_library(
    payload: BomLibraryConfirm,
    request: Request,
    session: Session = Depends(get_db),
):
    preview = request.app.state.import_previews.get(payload.token)
    if preview is None or preview[0] != "bom_library":
        raise BusinessRuleError("建库预览已失效，请重新选择文件")
    overwrite_fields = {
        value.supplier_part: set(value.fields)
        for value in payload.overwrites
    }
    result = import_bom_library(
        session,
        parsed=preview[2],
        overwrite_fields=overwrite_fields,
    )
    request.app.state.import_previews.pop(payload.token, None)
    return {
        "created_count": result.created_count,
        "reused_count": result.reused_count,
        "warnings": result.warnings,
    }
