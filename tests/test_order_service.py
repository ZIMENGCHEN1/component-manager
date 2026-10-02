import pytest

from app.importers.order import parse_lcsc_order
from app.models import Component, Order, OrderItem, StockMovement
from app.services.storage import create_box


def require_order_service():
    try:
        from app.services import BusinessRuleError
        from app.services.orders import assign_order_item_to_cell, import_order
    except ModuleNotFoundError as exc:
        pytest.fail(f"order service is not implemented: {exc}")
    return import_order, assign_order_item_to_cell, BusinessRuleError


def test_order_import_matches_and_queues_unknown_parts(db_session, order_file):
    import_order, _, _ = require_order_service()
    db_session.add(Component(supplier="LCSC", supplier_part="C1001", comment="10k", footprint="0603"))
    db_session.commit()

    order = import_order(db_session, file_name="sample_order.xls", parsed=parse_lcsc_order(order_file))
    by_code = {item.supplier_part: item for item in order.items}

    assert by_code["C1001"].status == "pending_location"
    assert by_code["C9999"].status == "unmatched"
    assert db_session.query(StockMovement).count() == 0


def test_assigning_pending_item_to_cell_adds_shipped_stock_once(db_session, order_file):
    import_order, assign_order_item_to_cell, BusinessRuleError = require_order_service()
    component = Component(supplier="LCSC", supplier_part="C1001", comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()
    box = create_box(db_session, name="电阻盒", rows=1, columns=1)
    order = import_order(db_session, file_name="sample_order.xls", parsed=parse_lcsc_order(order_file))
    item = next(value for value in order.items if value.supplier_part == "C1001")

    assign_order_item_to_cell(db_session, item.id, box.cells[0].id)

    assert item.status == "stocked"
    assert component.available_quantity == 8
    assert box.cells[0].component_id == component.id
    assert db_session.query(StockMovement).filter_by(movement_type="order_in").count() == 1
    with pytest.raises(BusinessRuleError, match="已经入库"):
        assign_order_item_to_cell(db_session, item.id, box.cells[0].id)


def test_order_for_located_component_stocks_immediately(db_session, order_file):
    import_order, _, _ = require_order_service()
    component = Component(supplier="LCSC", supplier_part="C1001", comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()
    box = create_box(db_session, name="电阻盒", rows=1, columns=1)
    box.cells[0].component = component
    db_session.commit()

    order = import_order(db_session, file_name="sample_order.xls", parsed=parse_lcsc_order(order_file))
    item = next(value for value in order.items if value.supplier_part == "C1001")

    assert item.status == "stocked"
    assert component.available_quantity == 8


def test_duplicate_order_number_is_rejected(db_session, order_file):
    import_order, _, BusinessRuleError = require_order_service()
    parsed = parse_lcsc_order(order_file)
    import_order(db_session, file_name="sample_order.xls", parsed=parsed)

    with pytest.raises(BusinessRuleError, match="已经导入"):
        import_order(db_session, file_name="sample_order.xls", parsed=parsed)

    assert db_session.query(Order).count() == 1
    assert db_session.query(OrderItem).count() == 2
