import pytest

from app.importers.bom import parse_bom
from app.models import Bom, BomItem, Component, StockMovement
from app.services.storage import assign_component, create_box


def require_bom_service():
    try:
        from app.services import BusinessRuleError
        from app.services.bom import import_bom, pick_bom_item
    except ModuleNotFoundError as exc:
        pytest.fail(f"BOM service is not implemented: {exc}")
    return import_bom, pick_bom_item, BusinessRuleError


def _seed_components(db_session, parsed):
    components = []
    for item in parsed.items:
        component = Component(
            supplier="LCSC",
            supplier_part=item.supplier_part,
            comment=item.comment,
            footprint=item.footprint,
        )
        db_session.add(component)
        components.append(component)
    db_session.commit()
    return components


def _locate_components(db_session, components):
    box = create_box(db_session, name="测试盒", rows=1, columns=len(components))
    for component, cell in zip(components, box.cells, strict=True):
        assign_component(db_session, component.id, cell.id)
    return box


def _seed_shared_candidate_bom(db_session, *, candidate_quantity: int):
    exact = Component(
        supplier="LCSC",
        supplier_part="A",
        comment="10kΩ",
        footprint="R0603",
        available_quantity=0,
    )
    candidate = Component(
        supplier="LCSC",
        supplier_part="B",
        comment="10kΩ",
        footprint="R0805",
        available_quantity=candidate_quantity,
    )
    bom = Bom(name="共享候选", file_name="shared.xlsx")
    source_item = BomItem(
        component=exact,
        supplier_part="A",
        comment="10kΩ",
        footprint="R0603",
        quantity=3,
        designators="R1, R2, R3",
    )
    native_item = BomItem(
        component=candidate,
        supplier_part="B",
        comment="10kΩ",
        footprint="R0805",
        quantity=5,
        designators="R4, R5, R6, R7, R8",
    )
    bom.items.extend([source_item, native_item])
    db_session.add_all([exact, candidate, bom])
    db_session.commit()
    _locate_components(db_session, [candidate])
    return bom, source_item, native_item, candidate


def test_bom_library_import_creates_components_without_pick_list(db_session, bom_file):
    try:
        from app.services.bom_library import import_bom_library
    except ModuleNotFoundError as exc:
        pytest.fail(f"BOM library service is not implemented: {exc}")

    result = import_bom_library(db_session, parsed=parse_bom(bom_file))

    assert result.created_count == 2
    assert result.reused_count == 0
    assert db_session.query(Component).count() == 2
    assert db_session.query(Bom).count() == 0
    assert all(component.available_quantity == 0 for component in db_session.query(Component).all())
    assert all(component.storage_cell is None for component in db_session.query(Component).all())


def _parsed_metadata_bom():
    from app.importers.bom import ParsedBom, ParsedBomItem

    return ParsedBom(items=[ParsedBomItem(
        supplier_part="C1001",
        comment="10kΩ",
        footprint="R0603",
        quantity=1,
        designators=["R1"],
        secondary_category="贴片电阻",
        description="BOM 中的新说明",
    )])


def test_bom_library_fills_blank_metadata_without_explicit_overwrite(db_session):
    from app.services.bom_library import import_bom_library

    component = Component(
        supplier="LCSC",
        supplier_part="C1001",
        comment="10kΩ",
        footprint="R0603",
        secondary_category="",
        description="",
    )
    db_session.add(component)
    db_session.commit()

    import_bom_library(db_session, parsed=_parsed_metadata_bom(), overwrite_fields={})

    assert component.secondary_category == "贴片电阻"
    assert component.description == "BOM 中的新说明"


def test_bom_library_only_overwrites_selected_conflicting_fields(db_session):
    from app.services.bom_library import import_bom_library

    component = Component(
        supplier="LCSC",
        supplier_part="C1001",
        comment="10kΩ",
        footprint="R0603",
        secondary_category="旧分类",
        description="旧说明",
    )
    db_session.add(component)
    db_session.commit()

    import_bom_library(
        db_session,
        parsed=_parsed_metadata_bom(),
        overwrite_fields={"C1001": {"description"}},
    )

    assert component.secondary_category == "旧分类"
    assert component.description == "BOM 中的新说明"


def test_bom_library_rejects_non_conflicting_overwrite_selection(db_session):
    from app.services import BusinessRuleError
    from app.services.bom_library import import_bom_library

    with pytest.raises(BusinessRuleError, match="覆盖选择无效"):
        import_bom_library(
            db_session,
            parsed=_parsed_metadata_bom(),
            overwrite_fields={"UNKNOWN": {"description"}},
        )


def test_pick_bom_keeps_category_and_description_snapshot(db_session):
    from app.importers.bom import ParsedBom, ParsedBomItem
    from app.services.bom import import_bom

    component = Component(
        supplier="LCSC",
        supplier_part="C1001",
        comment="10kΩ",
        footprint="R0603",
        secondary_category="库存旧分类",
        description="库存旧说明",
    )
    db_session.add(component)
    db_session.commit()
    parsed = ParsedBom(items=[ParsedBomItem(
        supplier_part="C1001",
        comment="10kΩ",
        footprint="R0603",
        quantity=1,
        designators=["R1"],
        secondary_category="BOM 分类",
        description="BOM 原始说明",
    )])

    bom = import_bom(db_session, name="快照测试", file_name="snapshot.xlsx", parsed=parsed)
    component.description = "库存后来修改"
    db_session.commit()

    assert bom.items[0].secondary_category == "BOM 分类"
    assert bom.items[0].description == "BOM 原始说明"
    assert bom.items[0].component.description == "库存后来修改"


def test_pick_bom_import_leaves_unknown_parts_unmatched(db_session, bom_file):
    import_bom, _, _ = require_bom_service()
    bom = import_bom(db_session, name="控制板", file_name="sample_bom.xlsx", parsed=parse_bom(bom_file))

    assert len(bom.items) == 2
    assert db_session.query(Component).count() == 0
    assert all(item.component is None for item in bom.items)


def test_pick_one_bom_item_deducts_only_that_item_once(db_session, bom_file):
    import_bom, pick_bom_item, BusinessRuleError = require_bom_service()
    parsed = parse_bom(bom_file)
    components = _seed_components(db_session, parsed)
    _locate_components(db_session, components)
    bom = import_bom(db_session, name="控制板", file_name="sample_bom.xlsx", parsed=parsed)
    for item in bom.items:
        item.component.available_quantity = item.quantity + 2
    db_session.commit()

    picked = pick_bom_item(db_session, bom.items[0].id)

    assert picked.id == bom.items[0].id
    assert bom.items[0].component.available_quantity == 2
    assert bom.items[1].component.available_quantity == bom.items[1].quantity + 2
    assert bom.status == "open"
    movement = db_session.query(StockMovement).one()
    assert movement.movement_type == "bom_item_out"
    assert movement.source_type == "bom_item"
    assert movement.source_id == bom.items[0].id
    with pytest.raises(BusinessRuleError, match="已经领取"):
        pick_bom_item(db_session, bom.items[0].id)


def test_last_bom_item_marks_bom_complete(db_session, bom_file):
    import_bom, pick_bom_item, _ = require_bom_service()
    parsed = parse_bom(bom_file)
    components = _seed_components(db_session, parsed)
    _locate_components(db_session, components)
    bom = import_bom(db_session, name="控制板", file_name="sample_bom.xlsx", parsed=parsed)
    for item in bom.items:
        item.component.available_quantity = item.quantity
    db_session.commit()

    pick_bom_item(db_session, bom.items[0].id)
    pick_bom_item(db_session, bom.items[1].id)

    assert bom.status == "picked"
    assert bom.picked_at is not None
    assert all(item.component.available_quantity == 0 for item in bom.items)


def test_pick_bom_item_rejects_shortage_without_movement(db_session, bom_file):
    import_bom, pick_bom_item, BusinessRuleError = require_bom_service()
    parsed = parse_bom(bom_file)
    components = _seed_components(db_session, parsed)
    _locate_components(db_session, components)
    bom = import_bom(db_session, name="控制板", file_name="sample_bom.xlsx", parsed=parsed)

    with pytest.raises(BusinessRuleError, match="库存不足"):
        pick_bom_item(db_session, bom.items[0].id)

    assert db_session.query(StockMovement).count() == 0


def test_pick_bom_item_rejects_unregistered_part_without_deduction(db_session, bom_file):
    import_bom, pick_bom_item, BusinessRuleError = require_bom_service()
    parsed = parse_bom(bom_file)
    registered = parsed.items[0]
    component = Component(
        supplier="LCSC",
        supplier_part=registered.supplier_part,
        comment=registered.comment,
        footprint=registered.footprint,
        available_quantity=registered.quantity,
    )
    db_session.add(component)
    db_session.commit()
    bom = import_bom(db_session, name="控制板", file_name="sample_bom.xlsx", parsed=parsed)
    unknown_item = next(item for item in bom.items if item.component is None)

    with pytest.raises(BusinessRuleError, match="未建档"):
        pick_bom_item(db_session, unknown_item.id)

    assert component.available_quantity == registered.quantity
    assert db_session.query(StockMovement).count() == 0


def test_normalize_comment_for_match_only_applies_approved_rules():
    from app.services.bom_matching import normalize_comment_for_match

    assert normalize_comment_for_match("  22μF   ±10%  ") == "22uf ±10%"
    assert normalize_comment_for_match("22µf ±10%") == "22uf ±10%"
    assert normalize_comment_for_match("22UF ±10%") == "22uf ±10%"
    assert normalize_comment_for_match("0.1uF") != normalize_comment_for_match("100nF")
    assert normalize_comment_for_match("") == ""


def test_comment_candidates_are_only_offered_when_exact_part_is_missing_or_short(db_session):
    from app.services.bom_matching import find_comment_candidates

    exact = Component(
        supplier="LCSC",
        supplier_part="C1001",
        comment="22uF",
        footprint="0603",
        available_quantity=1,
    )
    enough = Component(
        supplier="LCSC",
        supplier_part="C2002",
        comment="22μf",
        footprint="0805",
        available_quantity=10,
    )
    short = Component(
        supplier="LCSC",
        supplier_part="C2003",
        comment="22µF",
        footprint="1206",
        available_quantity=1,
    )
    wrong = Component(
        supplier="LCSC",
        supplier_part="C3003",
        comment="10uF",
        footprint="0603",
        available_quantity=20,
    )
    db_session.add_all([exact, enough, short, wrong])
    db_session.commit()
    item = BomItem(supplier_part="C1001", comment="22µF", footprint="0603", quantity=2)

    candidates = find_comment_candidates(db_session, item)

    assert [value.id for value in candidates] == [enough.id, short.id]
    assert candidates[0].footprint == "0805"


def test_comment_candidates_are_hidden_when_exact_part_has_enough_stock(db_session):
    from app.services.bom_matching import find_comment_candidates

    exact = Component(
        supplier="LCSC",
        supplier_part="C1001",
        comment="22uF",
        footprint="0603",
        available_quantity=2,
    )
    alternate = Component(
        supplier="LCSC",
        supplier_part="C2002",
        comment="22uF",
        footprint="0805",
        available_quantity=20,
    )
    db_session.add_all([exact, alternate])
    db_session.commit()
    item = BomItem(supplier_part="C1001", comment="22uF", footprint="0603", quantity=2)

    assert find_comment_candidates(db_session, item) == []


def test_comment_candidates_are_offered_when_exact_part_stock_is_zero(db_session):
    from app.services.bom_matching import find_comment_candidates

    exact = Component(
        supplier="LCSC",
        supplier_part="C1001",
        comment="22uF",
        footprint="0603",
        available_quantity=0,
    )
    alternate = Component(
        supplier="LCSC",
        supplier_part="C2002",
        comment="22μF",
        footprint="0805",
        available_quantity=20,
    )
    db_session.add_all([exact, alternate])
    db_session.commit()
    item = BomItem(supplier_part="C1001", comment="22µF", footprint="0603", quantity=2)

    assert [value.id for value in find_comment_candidates(db_session, item)] == [alternate.id]


def test_comment_candidates_require_nonempty_comment(db_session):
    from app.services.bom_matching import find_comment_candidates

    db_session.add(Component(supplier="LCSC", supplier_part="C2002", comment="", available_quantity=20))
    db_session.commit()
    item = BomItem(supplier_part="C1001", comment="", footprint="0603", quantity=2)

    assert find_comment_candidates(db_session, item) == []


def _create_candidate_for_first_bom_item(
    db_session,
    bom_file,
    *,
    comment: str | None = None,
    quantity: int = 20,
    locate: bool = True,
):
    import_bom, _, _ = require_bom_service()
    parsed = parse_bom(bom_file)
    candidate = Component(
        supplier="LCSC",
        supplier_part="C9001",
        comment=comment if comment is not None else f"  {parsed.items[0].comment.upper()}  ",
        footprint="DIFFERENT-FOOTPRINT",
        available_quantity=quantity,
    )
    db_session.add(candidate)
    db_session.commit()
    if locate:
        _locate_components(db_session, [candidate])
    bom = import_bom(db_session, name="替代测试", file_name="sample_bom.xlsx", parsed=parsed)
    return bom, bom.items[0], candidate, parsed.items[0]


def test_select_bom_item_candidate_changes_only_current_selection(db_session, bom_file):
    from app.services.bom_matching import select_bom_item_candidate

    _, item, candidate, parsed_item = _create_candidate_for_first_bom_item(db_session, bom_file)

    selected = select_bom_item_candidate(db_session, item.id, candidate.id)

    assert selected.component_id == candidate.id
    assert selected.supplier_part == parsed_item.supplier_part
    assert selected.comment == parsed_item.comment
    assert selected.footprint == parsed_item.footprint
    assert candidate.available_quantity == 20
    assert db_session.query(StockMovement).count() == 0


def test_select_candidate_checks_all_pending_demand_for_same_component(db_session):
    from app.services import BusinessRuleError
    from app.services.bom_matching import select_bom_item_candidate

    _, source_item, _, candidate = _seed_shared_candidate_bom(
        db_session,
        candidate_quantity=7,
    )

    with pytest.raises(BusinessRuleError, match="合计需要 8 件"):
        select_bom_item_candidate(db_session, source_item.id, candidate.id)

    assert source_item.component.supplier_part == "A"
    assert candidate.available_quantity == 7


def test_select_candidate_accepts_exact_aggregate_quantity(db_session):
    from app.services.bom_matching import select_bom_item_candidate

    _, source_item, _, candidate = _seed_shared_candidate_bom(
        db_session,
        candidate_quantity=8,
    )

    selected = select_bom_item_candidate(db_session, source_item.id, candidate.id)

    assert selected.component_id == candidate.id
    assert selected.supplier_part == "A"
    assert selected.designators == "R1, R2, R3"
    assert candidate.available_quantity == 8


def test_select_bom_item_candidate_rejects_mismatched_comment(db_session, bom_file):
    from app.services import BusinessRuleError
    from app.services.bom_matching import select_bom_item_candidate

    _, item, candidate, _ = _create_candidate_for_first_bom_item(
        db_session,
        bom_file,
        comment="different value",
    )

    with pytest.raises(BusinessRuleError, match="Comment"):
        select_bom_item_candidate(db_session, item.id, candidate.id)


def test_select_bom_item_candidate_rejects_insufficient_stock(db_session, bom_file):
    from app.services import BusinessRuleError
    from app.services.bom_matching import select_bom_item_candidate

    _, item, candidate, _ = _create_candidate_for_first_bom_item(
        db_session,
        bom_file,
        quantity=1,
    )

    with pytest.raises(BusinessRuleError, match="库存不足"):
        select_bom_item_candidate(db_session, item.id, candidate.id)


def test_select_bom_item_candidate_allows_missing_location_without_deduction(db_session, bom_file):
    from app.services.bom_matching import select_bom_item_candidate

    _, item, candidate, _ = _create_candidate_for_first_bom_item(
        db_session,
        bom_file,
        locate=False,
    )

    selected = select_bom_item_candidate(db_session, item.id, candidate.id)

    assert selected.component_id == candidate.id
    assert selected.component.storage_cell is None
    assert candidate.available_quantity == 20
    assert db_session.query(StockMovement).count() == 0


def test_select_bom_item_candidate_rejects_when_exact_stock_is_enough(db_session, bom_file):
    from app.services import BusinessRuleError
    from app.services.bom_matching import select_bom_item_candidate

    import_bom, _, _ = require_bom_service()
    parsed = parse_bom(bom_file)
    exact = Component(
        supplier="LCSC",
        supplier_part=parsed.items[0].supplier_part,
        comment=parsed.items[0].comment,
        footprint=parsed.items[0].footprint,
        available_quantity=parsed.items[0].quantity,
    )
    candidate = Component(
        supplier="LCSC",
        supplier_part="C9001",
        comment=parsed.items[0].comment,
        footprint="DIFFERENT",
        available_quantity=20,
    )
    db_session.add_all([exact, candidate])
    db_session.commit()
    _locate_components(db_session, [exact, candidate])
    bom = import_bom(db_session, name="精确料充足", file_name="sample_bom.xlsx", parsed=parsed)

    with pytest.raises(BusinessRuleError, match="无需替代"):
        select_bom_item_candidate(db_session, bom.items[0].id, candidate.id)


def test_select_bom_item_candidate_rejects_already_picked_item(db_session, bom_file):
    from app.services import BusinessRuleError
    from app.services.bom_matching import select_bom_item_candidate

    import_bom, pick_bom_item, _ = require_bom_service()
    parsed = parse_bom(bom_file)
    exact = Component(
        supplier="LCSC",
        supplier_part=parsed.items[0].supplier_part,
        comment=parsed.items[0].comment,
        footprint=parsed.items[0].footprint,
        available_quantity=parsed.items[0].quantity,
    )
    candidate = Component(
        supplier="LCSC",
        supplier_part="C9001",
        comment=parsed.items[0].comment,
        footprint="DIFFERENT",
        available_quantity=20,
    )
    db_session.add_all([exact, candidate])
    db_session.commit()
    _locate_components(db_session, [exact, candidate])
    bom = import_bom(db_session, name="已领料", file_name="sample_bom.xlsx", parsed=parsed)
    pick_bom_item(db_session, bom.items[0].id)

    with pytest.raises(BusinessRuleError, match="已经领料"):
        select_bom_item_candidate(db_session, bom.items[0].id, candidate.id)


def test_candidate_selection_feeds_existing_pick_flow(db_session, bom_file):
    from app.services.bom_matching import select_bom_item_candidate

    _, pick_bom_item, _ = require_bom_service()
    _, item, candidate, parsed_item = _create_candidate_for_first_bom_item(db_session, bom_file)
    selected = select_bom_item_candidate(db_session, item.id, candidate.id)
    before = candidate.available_quantity

    picked = pick_bom_item(db_session, selected.id)

    assert candidate.available_quantity == before - item.quantity
    movement = db_session.query(StockMovement).one()
    assert movement.component_id == candidate.id
    assert movement.source_type == "bom_item"
    assert movement.source_id == item.id
    assert picked.supplier_part == parsed_item.supplier_part
    assert picked.component_id == candidate.id


def test_pick_shared_component_group_deducts_total_and_tracks_each_bom_item(db_session):
    from app.services.bom import build_pick_groups, pick_bom_item
    from app.services.bom_matching import select_bom_item_candidate

    bom, source_item, native_item, candidate = _seed_shared_candidate_bom(
        db_session,
        candidate_quantity=10,
    )
    select_bom_item_candidate(db_session, source_item.id, candidate.id)

    groups = build_pick_groups(bom.items, set())
    group = next(iter(groups.values()))

    assert len(groups) == 1
    assert group.pending_quantity == 8
    assert [value.supplier_part for value in group.pending_items] == ["A", "B"]

    pick_bom_item(db_session, source_item.id)

    assert candidate.available_quantity == 2
    movements = db_session.query(StockMovement).order_by(StockMovement.source_id).all()
    assert len(movements) == 2
    assert {value.source_id for value in movements} == {source_item.id, native_item.id}
    assert {value.quantity_delta for value in movements} == {-3, -5}
    assert all(value.component_id == candidate.id for value in movements)
    assert bom.status == "picked"


def test_pick_shared_component_group_rolls_back_as_one_transaction(db_session, monkeypatch):
    import app.services.bom as bom_service
    from app.services.bom_matching import select_bom_item_candidate

    _, source_item, _, candidate = _seed_shared_candidate_bom(
        db_session,
        candidate_quantity=10,
    )
    select_bom_item_candidate(db_session, source_item.id, candidate.id)
    original_apply = bom_service.apply_stock_change
    call_count = 0

    def fail_on_second_item(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("模拟第二条流水失败")
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(bom_service, "apply_stock_change", fail_on_second_item)

    with pytest.raises(RuntimeError, match="第二条流水失败"):
        bom_service.pick_bom_item(db_session, source_item.id)

    db_session.refresh(candidate)
    assert candidate.available_quantity == 10
    assert db_session.query(StockMovement).count() == 0
