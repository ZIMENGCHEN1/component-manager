from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Component, StorageCell
from app.routes.serializers import component_dict
from app.schemas.components import ComponentCreate, ComponentUpdate, StockAdjustment
from app.services.components import create_component, delete_component, update_component
from app.services.inventory import adjust_stock


router = APIRouter(prefix="/api/components", tags=["components"])


def _component_query():
    return select(Component).options(
        selectinload(Component.storage_cell).selectinload(StorageCell.box)
    )


@router.get("")
def list_components(session: Session = Depends(get_db)):
    components = session.execute(_component_query().order_by(Component.id.desc())).scalars().all()
    return [component_dict(component) for component in components]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_component(payload: ComponentCreate, session: Session = Depends(get_db)):
    component = create_component(session, **payload.model_dump())
    component = session.execute(_component_query().where(Component.id == component.id)).scalar_one()
    return component_dict(component)


@router.patch("/{component_id}")
def edit_component(component_id: int, payload: ComponentUpdate, session: Session = Depends(get_db)):
    component = update_component(session, component_id, **payload.model_dump(exclude_unset=True))
    component = session.execute(_component_query().where(Component.id == component.id)).scalar_one()
    return component_dict(component)


@router.post("/{component_id}/adjust-stock")
def change_component_stock(component_id: int, payload: StockAdjustment, session: Session = Depends(get_db)):
    adjust_stock(session, component_id, payload.delta, note=payload.note)
    component = session.execute(_component_query().where(Component.id == component_id)).scalar_one()
    return component_dict(component)


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_component(component_id: int, session: Session = Depends(get_db)):
    delete_component(session, component_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
