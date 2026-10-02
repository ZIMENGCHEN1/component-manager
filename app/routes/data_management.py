from datetime import datetime
from pathlib import Path
import tempfile

from fastapi import APIRouter, Request, Response, UploadFile
from sqlalchemy.engine import make_url

from app import db
from app.services import BusinessRuleError
from app.services.data_management import build_excel_export, create_database_backup, restore_database


router = APIRouter(prefix="/api/data", tags=["data"])


def _database_url() -> str:
    return db.engine.url.render_as_string(hide_password=False)


def _backup_directory(database_url: str) -> Path:
    return Path(make_url(database_url).database).resolve().parent / "backups"


@router.get("/export.xlsx")
def export_excel():
    with db.SessionLocal() as session:
        content = build_excel_export(session)
    filename = f"component-inventory-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/backup")
def download_backup():
    content = create_database_backup(_database_url())
    filename = f"component-inventory-{datetime.now():%Y%m%d-%H%M%S}.db"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/restore")
async def upload_restore(request: Request, file: UploadFile):
    if Path(file.filename or "").suffix.lower() != ".db":
        raise BusinessRuleError("恢复只支持 .db 备份文件")
    uploaded_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as target:
            target.write(await file.read())
            uploaded_path = Path(target.name)
        database_url = _database_url()
        db.engine.dispose()
        safety_backup = restore_database(database_url, uploaded_path, _backup_directory(database_url))
        db.engine.dispose()
        db.init_db()
        request.app.state.import_previews.clear()
    finally:
        if uploaded_path is not None:
            uploaded_path.unlink(missing_ok=True)
    return {
        "message": "数据库已恢复",
        "safety_backup": safety_backup.name,
    }
