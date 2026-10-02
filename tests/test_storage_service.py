import pytest

from app.models import Component


def require_storage_service():
    try:
        from app.services import BusinessRuleError
        from app.services.storage import assign_component, create_box
    except ModuleNotFoundError as exc:
        pytest.fail(f"storage service is not implemented: {exc}")
    return create_box, assign_component, BusinessRuleError


def test_create_box_generates_named_grid(db_session):
    create_box, _, _ = require_storage_service()
    box = create_box(db_session, name="元件盒 A", rows=4, columns=6)

    assert len(box.cells) == 24
    assert box.cells[0].label == "A1"
    assert box.cells[-1].label == "D6"


def test_occupied_cell_rejects_second_component(db_session):
    create_box, assign_component, BusinessRuleError = require_storage_service()
    box = create_box(db_session, name="元件盒 A", rows=1, columns=1)
    first = Component(comment="10k", footprint="0603")
    second = Component(comment="1k", footprint="0603")
    db_session.add_all([first, second])
    db_session.commit()

    assign_component(db_session, first.id, box.cells[0].id)
    with pytest.raises(BusinessRuleError, match="占用"):
        assign_component(db_session, second.id, box.cells[0].id)

    assert box.cells[0].component_id == first.id
