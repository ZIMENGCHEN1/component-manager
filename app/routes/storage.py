from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import StorageBox, StorageCell
from app.routes.serializers import box_dict
from app.schemas.storage import BoxCreate, BoxUpdate, CellAssignment, CellUpdate
from app.services import BusinessRuleError
from app.services.storage import assign_component, create_box, delete_box, update_box, update_cell


router = APIRouter(prefix="/api/storage", tags=["storage"])


def _box_query():
    return select(StorageBox).options(
        selectinload(StorageBox.cells).selectinload(StorageCell.component)
    )


@router.get("/boxes")
def list_boxes(session: Session = Depends(get_db)):
    boxes = session.execute(_box_query().order_by(StorageBox.name)).scalars().all()
    return [box_dict(box) for box in boxes]


@router.post("/boxes", status_code=status.HTTP_201_CREATED)
def add_box(payload: BoxCreate, session: Session = Depends(get_db)):
    box = create_box(session, name=payload.name, rows=payload.rows, columns=payload.columns)
    return box_dict(box)


@router.patch("/boxes/{box_id}")
def edit_box(box_id: int, payload: BoxUpdate, session: Session = Depends(get_db)):
    box = update_box(
        session,
        box_id,
        name=payload.name,
        rows=payload.rows,
        columns=payload.columns,
    )
    return box_dict(box)


@router.delete("/boxes/{box_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_box(box_id: int, session: Session = Depends(get_db)):
    delete_box(session, box_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cells/{cell_id}/assign-component")
def put_component_in_cell(cell_id: int, payload: CellAssignment, session: Session = Depends(get_db)):
    if payload.component_id is None:
        raise BusinessRuleError("请选择元件")
    cell = assign_component(session, payload.component_id, cell_id)
    return {"id": cell.id, "label": cell.label, "component_id": cell.component_id}


@router.patch("/cells/{cell_id}")
def edit_cell(cell_id: int, payload: CellUpdate, session: Session = Depends(get_db)):
    cell = update_cell(
        session,
        cell_id,
        label=payload.label,
        component_id=payload.component_id,
    )
    return {"id": cell.id, "label": cell.label, "component_id": cell.component_id}
