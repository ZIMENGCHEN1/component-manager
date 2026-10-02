from decimal import Decimal

import pytest


def require_order_importer():
    try:
        from app.importers.order import parse_lcsc_order
    except ModuleNotFoundError as exc:
        pytest.fail(f"order importer is not implemented: {exc}")
    return parse_lcsc_order


def test_order_parser_finds_dynamic_header_and_uses_shipped_quantity(order_file):
    parse_lcsc_order = require_order_importer()
    result = parse_lcsc_order(order_file)

    assert result.order_number == "SO-DEMO-001"
    assert len(result.items) == 2
    assert result.items[0].supplier_part == "C1001"
    assert result.items[0].ordered_quantity == 10
    assert result.items[0].shipped_quantity == 8
    assert result.items[0].unit_price == Decimal("0.01")


def test_order_parser_keeps_unknown_supplier_part(order_file):
    parse_lcsc_order = require_order_importer()
    result = parse_lcsc_order(order_file)

    assert result.items[1].supplier_part == "C9999"
    assert result.items[1].shipped_quantity == 5
