import pytest

from app.models import Component, StockMovement


def require_inventory_service():
    try:
        from app.services import BusinessRuleError
        from app.services.inventory import adjust_stock, apply_stock_change, reverse_stock_movement
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"inventory service is not implemented: {exc}")
    return adjust_stock, apply_stock_change, reverse_stock_movement, BusinessRuleError


def test_adjust_stock_updates_quantity_and_writes_movement(db_session):
    adjust_stock, _, _, _ = require_inventory_service()
    component = Component(comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()

    adjust_stock(db_session, component.id, 12, note="首次盘点")

    assert component.available_quantity == 12
    movement = db_session.query(StockMovement).one()
    assert movement.quantity_delta == 12
    assert movement.movement_type == "adjustment"


def test_adjust_stock_rejects_negative_inventory(db_session):
    adjust_stock, _, _, BusinessRuleError = require_inventory_service()
    component = Component(comment="10k", footprint="0603", available_quantity=3)
    db_session.add(component)
    db_session.commit()

    with pytest.raises(BusinessRuleError, match="不足"):
        adjust_stock(db_session, component.id, -4, note="错误盘点")

    assert component.available_quantity == 3
    assert db_session.query(StockMovement).count() == 0


def test_reverse_adjustment_writes_compensating_movement(db_session):
    adjust_stock, _, reverse_stock_movement, _ = require_inventory_service()
    component = Component(comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()
    original = adjust_stock(db_session, component.id, 12, note="首次盘点")

    reversal = reverse_stock_movement(db_session, original.id)

    assert component.available_quantity == 0
    assert reversal.quantity_delta == -12
    assert reversal.movement_type == "adjustment_reversal"
    assert reversal.source_type == "stock_movement"
    assert reversal.source_id == original.id


def test_reverse_adjustment_rejects_second_reversal(db_session):
    adjust_stock, _, reverse_stock_movement, BusinessRuleError = require_inventory_service()
    component = Component(comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()
    original = adjust_stock(db_session, component.id, 3)
    reverse_stock_movement(db_session, original.id)

    with pytest.raises(BusinessRuleError, match="已经撤销"):
        reverse_stock_movement(db_session, original.id)


def test_reverse_stock_movement_rejects_non_adjustment(db_session):
    _, apply_stock_change, reverse_stock_movement, BusinessRuleError = require_inventory_service()
    component = Component(comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()
    movement = apply_stock_change(db_session, component, 5, "order_in")
    db_session.commit()

    with pytest.raises(BusinessRuleError, match="手动调整"):
        reverse_stock_movement(db_session, movement.id)


def test_reverse_positive_adjustment_rejects_negative_inventory(db_session):
    adjust_stock, apply_stock_change, reverse_stock_movement, BusinessRuleError = require_inventory_service()
    component = Component(comment="10k", footprint="0603")
    db_session.add(component)
    db_session.commit()
    original = adjust_stock(db_session, component.id, 5)
    apply_stock_change(db_session, component, -5, "bom_item_out")
    db_session.commit()

    with pytest.raises(BusinessRuleError, match="库存不足"):
        reverse_stock_movement(db_session, original.id)

    assert component.available_quantity == 0
