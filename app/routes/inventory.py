from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.inventory import reverse_stock_movement


router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/movements/{movement_id}/reverse")
def reverse_movement(movement_id: int, session: Session = Depends(get_db)):
    movement = reverse_stock_movement(session, movement_id)
    return {
        "id": movement.id,
        "component_id": movement.component_id,
        "quantity_delta": movement.quantity_delta,
        "movement_type": movement.movement_type,
        "source_type": movement.source_type,
        "source_id": movement.source_id,
        "note": movement.note,
    }
