import pytest


def require_component_service():
    try:
        from app.services.components import create_component, update_component
    except ModuleNotFoundError as exc:
        pytest.fail(f"component service is not implemented: {exc}")
    return create_component, update_component


def test_manual_component_can_be_created_without_supplier_part(db_session):
    create_component, _ = require_component_service()
    component = create_component(db_session, comment="通用排针", footprint="P2.54")

    assert component.id is not None
    assert component.supplier_part is None
    assert component.available_quantity == 0


def test_component_can_be_updated_without_changing_stock(db_session):
    create_component, update_component = require_component_service()
    component = create_component(db_session, comment="10k", footprint="0603")
    updated = update_component(db_session, component.id, comment="10kΩ ±1%")

    assert updated.comment == "10kΩ ±1%"
    assert updated.available_quantity == 0


def test_component_metadata_can_be_created_and_updated(db_session):
    create_component, update_component = require_component_service()
    component = create_component(
        db_session,
        comment="10k",
        footprint="0603",
        secondary_category="贴片电阻",
        description="厚膜电阻 10kΩ ±1%",
    )

    assert component.secondary_category == "贴片电阻"
    assert component.description == "厚膜电阻 10kΩ ±1%"

    updated = update_component(
        db_session,
        component.id,
        description="薄膜电阻 10kΩ ±0.1%",
    )
    assert updated.description == "薄膜电阻 10kΩ ±0.1%"
