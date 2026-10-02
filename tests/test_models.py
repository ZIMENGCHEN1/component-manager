import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def require_models():
    try:
        from app.db import Base
        from app.models import Component, StorageBox, StorageCell
    except ModuleNotFoundError as exc:
        pytest.fail(f"model layer is not implemented: {exc}")
    return Base, Component, StorageBox, StorageCell


def test_supplier_part_is_unique():
    Base, Component, _, _ = require_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Component(supplier="LCSC", supplier_part="C1", comment="A", footprint="0603"))
        session.commit()
        session.add(Component(supplier="LCSC", supplier_part="C1", comment="B", footprint="0805"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_cell_and_component_are_one_to_one():
    Base, Component, StorageBox, StorageCell = require_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        box = StorageBox(name="电阻盒", rows=2, columns=3)
        component = Component(comment="10k", footprint="0603")
        cell = StorageCell(
            box=box,
            row_index=0,
            column_index=0,
            label="A1",
            component=component,
        )
        session.add_all([box, component, cell])
        session.commit()

        assert component.storage_cell.label == "A1"
        assert cell.component.comment == "10k"


def test_component_and_bom_item_metadata_default_to_empty_strings():
    from app.db import Base
    from app.models import Bom, BomItem, Component

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        component = Component(comment="10k", footprint="0603")
        bom = Bom(name="defaults", file_name="defaults.xlsx")
        item = BomItem(
            supplier_part="C1001",
            comment="10k",
            footprint="0603",
            quantity=1,
        )
        bom.items.append(item)
        session.add_all([component, bom])
        session.flush()

        assert component.secondary_category == ""
        assert component.description == ""
        assert item.secondary_category == ""
        assert item.description == ""
    engine.dispose()


def test_metadata_column_migration_is_idempotent_for_existing_sqlite_database(tmp_path):
    from app.db import ensure_metadata_columns

    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE components (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE bom_items (id INTEGER PRIMARY KEY)"))

    ensure_metadata_columns(engine)
    ensure_metadata_columns(engine)

    component_columns = {value["name"] for value in inspect(engine).get_columns("components")}
    bom_item_columns = {value["name"] for value in inspect(engine).get_columns("bom_items")}
    assert {"secondary_category", "description"} <= component_columns
    assert {"secondary_category", "description"} <= bom_item_columns
    engine.dispose()
