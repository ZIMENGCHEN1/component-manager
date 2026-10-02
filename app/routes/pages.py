from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Bom, BomItem, Component, Order, OrderItem, StockMovement, StorageBox, StorageCell
from app.services.bom import build_pick_groups
from app.services.bom_matching import find_comment_candidates, required_quantity_for_candidate


router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _render(request: Request, name: str, **context):
    return templates.TemplateResponse(request=request, name=name, context=context)


def _all_components(session: Session):
    return session.execute(
        select(Component)
        .options(selectinload(Component.storage_cell).selectinload(StorageCell.box))
        .order_by(Component.supplier_part, Component.id)
    ).scalars().all()


def _all_boxes(session: Session):
    return session.execute(
        select(StorageBox)
        .options(selectinload(StorageBox.cells).selectinload(StorageCell.component))
        .order_by(StorageBox.name)
    ).scalars().all()


def _bom_item_metadata(
    item: BomItem,
    source_component: Component | None,
) -> dict[str, object]:
    category_from_library = bool(
        not item.secondary_category
        and source_component
        and source_component.secondary_category
    )
    description_from_library = bool(
        not item.description
        and source_component
        and source_component.description
    )
    return {
        "secondary_category": item.secondary_category or (
            source_component.secondary_category if category_from_library else ""
        ),
        "description": item.description or (
            source_component.description if description_from_library else ""
        ),
        "category_from_library": category_from_library,
        "description_from_library": description_from_library,
    }


@router.get("/")
def dashboard(request: Request, session: Session = Depends(get_db)):
    stats = {
        "component_kinds": session.scalar(select(func.count(Component.id))) or 0,
        "total_pieces": session.scalar(select(func.coalesce(func.sum(Component.available_quantity), 0))) or 0,
        "pending_location": session.scalar(
            select(func.count(OrderItem.id)).where(OrderItem.status == "pending_location")
        ) or 0,
        "unmatched": session.scalar(
            select(func.count(OrderItem.id)).where(OrderItem.status == "unmatched")
        ) or 0,
    }
    recent_boms = session.execute(select(Bom).order_by(Bom.id.desc()).limit(5)).scalars().all()
    return _render(request, "dashboard.html", stats=stats, recent_boms=recent_boms)


@router.get("/components")
def components_page(
    request: Request,
    q: str = "",
    page: int = 1,
    session: Session = Depends(get_db),
):
    page_size = 50
    keyword = q.strip()
    component_statement = (
        select(Component)
        .outerjoin(Component.storage_cell)
        .outerjoin(StorageCell.box)
    )
    count_statement = (
        select(func.count(Component.id))
        .select_from(Component)
        .outerjoin(Component.storage_cell)
        .outerjoin(StorageCell.box)
    )
    if keyword:
        pattern = f"%{keyword}%"
        search_condition = or_(
            Component.supplier_part.ilike(pattern),
            Component.comment.ilike(pattern),
            Component.footprint.ilike(pattern),
            Component.manufacturer_part.ilike(pattern),
            Component.secondary_category.ilike(pattern),
            Component.description.ilike(pattern),
            StorageBox.name.ilike(pattern),
            StorageCell.label.ilike(pattern),
        )
        component_statement = component_statement.where(search_condition)
        count_statement = count_statement.where(search_condition)

    total_components = session.scalar(count_statement) or 0
    page_count = max(1, (total_components + page_size - 1) // page_size)
    current_page = min(max(page, 1), page_count)
    components = session.execute(
        component_statement
        .options(selectinload(Component.storage_cell).selectinload(StorageCell.box))
        .order_by(Component.supplier_part, Component.id)
        .offset((current_page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return _render(
        request,
        "components.html",
        components=components,
        q=keyword,
        total_components=total_components,
        page=current_page,
        page_count=page_count,
        page_numbers=range(
            max(1, current_page - 2),
            min(page_count, current_page + 2) + 1,
        ),
    )


@router.get("/bom-library")
def bom_library_page(request: Request, session: Session = Depends(get_db)):
    return RedirectResponse(url="/components?show_bom_import=1", status_code=307)


@router.get("/storage")
def storage_page(request: Request, session: Session = Depends(get_db)):
    return _render(
        request,
        "storage.html",
        boxes=_all_boxes(session),
        components=_all_components(session),
    )


@router.get("/boms")
def boms_page(
    request: Request,
    bom_id: int | None = None,
    expanded: bool = False,
    session: Session = Depends(get_db),
):
    boms = session.execute(select(Bom).order_by(Bom.id.desc())).scalars().all()
    selected_id = bom_id or (boms[0].id if boms else None)
    selected = None
    if selected_id is not None:
        selected = session.execute(
            select(Bom)
            .options(
                selectinload(Bom.items)
                .selectinload(BomItem.component)
                .selectinload(Component.storage_cell)
                .selectinload(StorageCell.box)
            )
            .where(Bom.id == selected_id)
        ).scalar_one_or_none()
    items = list(selected.items) if selected else []
    source_parts = {item.supplier_part for item in items}
    source_components = session.execute(
        select(Component).where(
            Component.supplier == "LCSC",
            Component.supplier_part.in_(source_parts),
        )
    ).scalars().all() if source_parts else []
    source_by_part = {
        component.supplier_part: component
        for component in source_components
    }
    item_metadata = {
        item.id: _bom_item_metadata(item, source_by_part.get(item.supplier_part))
        for item in items
    }
    picked_item_ids: set[int] = set()
    if selected is not None:
        if selected.status == "picked":
            picked_item_ids = {item.id for item in selected.items}
        else:
            picked_item_ids = set(session.execute(
                select(StockMovement.source_id).where(
                    StockMovement.source_type == "bom_item",
                    StockMovement.source_id.in_([item.id for item in selected.items]),
                )
            ).scalars())
    pending_source_quantity_by_part: dict[str, int] = {}
    for item in items:
        if item.id not in picked_item_ids:
            pending_source_quantity_by_part[item.supplier_part] = (
                pending_source_quantity_by_part.get(item.supplier_part, 0)
                + item.quantity
            )
    needs_substitute_by_item = {
        item.id: item.id not in picked_item_ids
        and (
            source_by_part.get(item.supplier_part) is None
            or source_by_part[item.supplier_part].available_quantity
            < pending_source_quantity_by_part[item.supplier_part]
        )
        for item in items
    }
    pick_groups = build_pick_groups(items, picked_item_ids)
    pending_quantity_by_component: dict[int, int] = {}
    for item in items:
        if item.id not in picked_item_ids and item.component_id is not None:
            pending_quantity_by_component[item.component_id] = (
                pending_quantity_by_component.get(item.component_id, 0) + item.quantity
            )
    candidates_by_item = {
        item.id: find_comment_candidates(session, item)
        for item in items
    }
    candidate_requirements = {
        item.id: {
            candidate.id: required_quantity_for_candidate(
                items,
                picked_item_ids,
                item,
                candidate.id,
            )
            for candidate in candidates_by_item[item.id]
        }
        for item in items
    }
    return _render(
        request,
        "boms.html",
        boms=boms,
        selected=selected,
        boxes=_all_boxes(session),
        pick_groups=pick_groups,
        pending_quantity_by_component=pending_quantity_by_component,
        picked_item_ids=picked_item_ids,
        candidates_by_item=candidates_by_item,
        candidate_requirements=candidate_requirements,
        item_metadata=item_metadata,
        needs_substitute_by_item=needs_substitute_by_item,
        expanded=expanded,
    )


@router.get("/orders")
def orders_page(request: Request, session: Session = Depends(get_db)):
    orders = session.execute(
        select(Order)
        .options(
            selectinload(Order.items)
            .selectinload(OrderItem.component)
            .selectinload(Component.storage_cell)
        )
        .order_by(Order.id.desc())
    ).scalars().all()
    return _render(
        request,
        "orders.html",
        orders=orders,
        components=_all_components(session),
        boxes=_all_boxes(session),
    )


@router.get("/inventory")
def inventory_page(
    request: Request,
    q: str = "",
    movement_type: str = "",
    session: Session = Depends(get_db),
):
    statement = (
        select(StockMovement)
        .join(Component)
        .options(
            selectinload(StockMovement.component)
            .selectinload(Component.storage_cell)
            .selectinload(StorageCell.box)
        )
        .order_by(StockMovement.id.desc())
        .limit(500)
    )
    keyword = q.strip()
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.where(or_(
            Component.supplier_part.ilike(pattern),
            Component.comment.ilike(pattern),
            Component.footprint.ilike(pattern),
            StockMovement.note.ilike(pattern),
        ))
    if movement_type:
        statement = statement.where(StockMovement.movement_type == movement_type)
    movements = session.execute(statement).scalars().all()

    running: dict[int, int] = {}
    balance_after: dict[int, int] = {}
    for movement_id, component_id, delta in session.execute(
        select(
            StockMovement.id,
            StockMovement.component_id,
            StockMovement.quantity_delta,
        ).order_by(StockMovement.id)
    ):
        running[component_id] = running.get(component_id, 0) + delta
        balance_after[movement_id] = running[component_id]

    reversed_ids = set(session.execute(
        select(StockMovement.source_id).where(
            StockMovement.movement_type == "adjustment_reversal",
            StockMovement.source_type == "stock_movement",
        )
    ).scalars())
    movement_types = [
        ("", "全部类型"),
        ("adjustment", "手动调整"),
        ("adjustment_reversal", "撤销调整"),
        ("order_in", "订单入库"),
        ("bom_item_out", "BOM 领料"),
    ]
    type_labels = dict(movement_types)
    return _render(
        request,
        "inventory.html",
        movements=movements,
        balance_after=balance_after,
        reversed_ids=reversed_ids,
        movement_types=movement_types,
        type_labels=type_labels,
        q=keyword,
        selected_type=movement_type,
    )


@router.get("/data-management")
def data_management_page(request: Request):
    return _render(request, "data_management.html")
