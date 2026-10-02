from app.models import Bom, Component, Order, OrderItem, StorageBox


def component_dict(component: Component) -> dict[str, object]:
    cell = component.storage_cell
    return {
        "id": component.id,
        "supplier": component.supplier,
        "supplier_part": component.supplier_part,
        "comment": component.comment,
        "footprint": component.footprint,
        "manufacturer": component.manufacturer,
        "manufacturer_part": component.manufacturer_part,
        "secondary_category": component.secondary_category,
        "description": component.description,
        "available_quantity": component.available_quantity,
        "location": None if cell is None else {
            "cell_id": cell.id,
            "box_id": cell.box_id,
            "box_name": cell.box.name if cell.box else "",
            "label": cell.label,
        },
    }


def box_dict(box: StorageBox) -> dict[str, object]:
    return {
        "id": box.id,
        "name": box.name,
        "rows": box.rows,
        "columns": box.columns,
        "cell_count": len(box.cells),
        "cells": [
            {
                "id": cell.id,
                "label": cell.label,
                "row": cell.row_index,
                "column": cell.column_index,
                "component_id": cell.component_id,
            }
            for cell in box.cells
        ],
    }


def order_item_dict(item: OrderItem) -> dict[str, object]:
    return {
        "id": item.id,
        "supplier_part": item.supplier_part,
        "manufacturer": item.manufacturer,
        "manufacturer_part": item.manufacturer_part,
        "order_package": item.order_package,
        "product_name": item.product_name,
        "ordered_quantity": item.ordered_quantity,
        "shipped_quantity": item.shipped_quantity,
        "status": item.status,
        "component_id": item.component_id,
    }


def order_dict(order: Order) -> dict[str, object]:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "file_name": order.file_name,
        "item_count": len(order.items),
        "items": [order_item_dict(item) for item in order.items],
    }


def bom_dict(bom: Bom, picked_item_ids: set[int] | None = None) -> dict[str, object]:
    picked_item_ids = picked_item_ids or set()
    return {
        "id": bom.id,
        "name": bom.name,
        "file_name": bom.file_name,
        "status": bom.status,
        "item_count": len(bom.items),
        "items": [
            {
                "id": item.id,
                "supplier_part": item.supplier_part,
                "quantity": item.quantity,
                "component_id": item.component_id,
                "picked": bom.status == "picked" or item.id in picked_item_ids,
            }
            for item in bom.items
        ],
    }
