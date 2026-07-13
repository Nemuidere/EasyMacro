"""
Builder-page tests for the screen-condition blocks (If/While) and Wait steps:
tree rendering with Then/Else headers, mixed int/branch path addressing,
drag-drop reconciliation across branches, wrap/ungroup/duplicate/edit ops,
undo, JSON round-trip, and context-menu enablement.
"""

import pytest
from PySide6.QtCore import Qt

import src.ui.pages.builder_page as bm
from src.models.action import (
    ClickAction,
    DelayAction,
    IfBlock,
    ImageCondition,
    LoopBlock,
    WaitAction,
    WhileBlock,
)
from src.services.macro_service import MacroService, init_macro_service
from src.ui.pages.builder_page import MacroBuilderPage, summarize_action, summarize_block


@pytest.fixture
def macro_service(tmp_path, initialized_event_bus):
    import src.services.macro_service as service_module
    service_module._macro_service = None
    service = init_macro_service(tmp_path / "macros.json")
    yield service
    service_module._macro_service = None


@pytest.fixture
def page(qapp, macro_service):
    p = MacroBuilderPage()
    p.reset()
    return p


def _cond(**overrides) -> ImageCondition:
    fields = {"image_file": "ref_test.png", "x1": 100, "y1": 200, "x2": 300, "y2": 260}
    fields.update(overrides)
    return ImageCondition(**fields)


def _if_block(**overrides) -> IfBlock:
    fields = {
        "condition": _cond(),
        "then_actions": [ClickAction(x=1, y=1)],
        "else_actions": [ClickAction(x=2, y=2)],
    }
    fields.update(overrides)
    return IfBlock(**fields)


class TestTreeRendering:
    def test_if_row_renders_two_locked_headers(self, page):
        page._actions = [_if_block()]
        page._refresh_list()

        if_item = page._action_list.topLevelItem(0)
        assert "If image found" in if_item.text(0)
        # Drops on the If row itself are disabled (that's what stops steps
        # landing beside the headers).
        assert not (if_item.flags() & Qt.ItemFlag.ItemIsDropEnabled)
        assert if_item.childCount() == 2

        then_header, else_header = if_item.child(0), if_item.child(1)
        assert then_header.text(0) == "Then"
        assert else_header.text(0) == "Else"
        for header, branch in ((then_header, "then"), (else_header, "else")):
            assert not (header.flags() & Qt.ItemFlag.ItemIsDragEnabled)
            assert header.flags() & Qt.ItemFlag.ItemIsDropEnabled
            assert header.data(0, page._BRANCH_ROLE) == branch
            assert header.data(0, page._OBJECT_ROLE) is page._actions[0]

    def test_branch_children_carry_mixed_paths(self, page):
        page._actions = [_if_block()]
        page._refresh_list()

        if_item = page._action_list.topLevelItem(0)
        then_step = if_item.child(0).child(0)
        else_step = if_item.child(1).child(0)
        assert then_step.data(0, Qt.ItemDataRole.UserRole) == [0, "then", 0]
        assert else_step.data(0, Qt.ItemDataRole.UserRole) == [0, "else", 0]

    def test_while_row_renders_body_like_loop(self, page):
        page._actions = [
            WhileBlock(condition=_cond(), actions=[ClickAction(x=1, y=1)],
                       max_iterations=5, timeout_seconds=30)
        ]
        page._refresh_list()

        row = page._action_list.topLevelItem(0)
        assert "While image found" in row.text(0)
        assert "≤5×" in row.text(0)
        assert "≤30s" in row.text(0)
        assert row.childCount() == 1
        assert row.flags() & Qt.ItemFlag.ItemIsDropEnabled

    def test_wait_summary(self, page):
        wait = WaitAction(condition=_cond(negate=True), timeout_ms=5000)
        text = summarize_action(wait)

        assert "Wait until image gone" in text
        assert "≤5s" in text

    def test_negated_block_labels(self):
        assert "not found" in summarize_block(IfBlock(condition=_cond(negate=True)))
        assert "not found" in summarize_block(WhileBlock(condition=_cond(negate=True)))


class TestPathAddressing:
    def test_container_for_else_branch(self, page):
        block = _if_block()
        page._actions = [block]

        assert page._container_for_path([0, "else", 0]) is block.else_actions
        assert page._container_for_path([0, "then", 0]) is block.then_actions

    def test_container_for_while_inside_then(self, page):
        inner = WhileBlock(condition=_cond(), actions=[ClickAction(x=7, y=7)])
        block = IfBlock(condition=_cond(), then_actions=[inner])
        page._actions = [block]

        assert page._container_for_path([0, "then", 0, 0]) is inner.actions

    def test_tree_item_lookup_inside_else(self, page):
        page._actions = [_if_block()]
        page._refresh_list()

        item = page._tree_item_at_path([0, "else", 0])

        assert item is not None
        assert item.data(0, Qt.ItemDataRole.UserRole) == [0, "else", 0]


class TestAddInsertion:
    def test_add_into_selected_if_goes_to_then(self, page, monkeypatch):
        new_click = ClickAction(x=42, y=42)
        monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])
        block = _if_block()
        page._actions = [block]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

        page._on_add()

        assert block.then_actions[-1] is new_click
        assert len(block.else_actions) == 1

    def test_add_into_selected_else_header(self, page, monkeypatch):
        new_click = ClickAction(x=42, y=42)
        monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])
        block = _if_block()
        page._actions = [block]
        page._refresh_list()
        else_header = page._action_list.topLevelItem(0).child(1)
        page._action_list.setCurrentItem(else_header)

        page._on_add()

        assert block.else_actions[-1] is new_click
        assert len(block.then_actions) == 1

    def test_add_empty_while_block_via_kind(self, page, monkeypatch):
        block = WhileBlock(condition=_cond())
        monkeypatch.setattr(bm.WhileBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.WhileBlockDialog, "result_actions", lambda self: [block])
        page._actions = [ClickAction(x=1, y=1)]
        page._refresh_list()

        page._on_add("while")

        assert page._actions[-1] is block

    def test_add_empty_loop_via_kind(self, page, monkeypatch):
        monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (4, True))
        page._actions = []
        page._refresh_list()

        page._on_add("loop")

        assert isinstance(page._actions[0], LoopBlock)
        assert page._actions[0].count == 4


class TestWrapOps:
    def test_wrap_selection_in_if_moves_steps_to_then(self, page, monkeypatch):
        created = IfBlock(condition=_cond())
        monkeypatch.setattr(bm.IfBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.IfBlockDialog, "result_action", lambda self: created)
        a, b, c = ClickAction(x=1, y=1), ClickAction(x=2, y=2), ClickAction(x=3, y=3)
        page._actions = [a, b, c]
        page._refresh_list()
        for row in (0, 1):
            page._action_list.topLevelItem(row).setSelected(True)

        page._on_wrap_in_if()

        assert page._actions == [created, c]
        assert created.then_actions == [a, b]
        assert created.else_actions == []

    def test_wrap_selection_in_while_moves_steps_to_body(self, page, monkeypatch):
        created = WhileBlock(condition=_cond())
        monkeypatch.setattr(bm.WhileBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.WhileBlockDialog, "result_action", lambda self: created)
        a, b = ClickAction(x=1, y=1), DelayAction(duration_ms=100)
        page._actions = [a, b]
        page._refresh_list()
        for row in (0, 1):
            page._action_list.topLevelItem(row).setSelected(True)

        page._on_wrap_in_while()

        assert page._actions == [created]
        assert created.actions == [a, b]

    def test_wrap_rejects_non_sibling_selection(self, page, monkeypatch):
        warnings = []
        monkeypatch.setattr(bm.QMessageBox, "warning", lambda *a, **k: warnings.append(a))
        block = _if_block()
        page._actions = [block, ClickAction(x=9, y=9)]
        page._refresh_list()
        # Select a step inside Then + the top-level click: different levels.
        page._tree_item_at_path([0, "then", 0]).setSelected(True)
        page._action_list.topLevelItem(1).setSelected(True)

        page._on_wrap_in_if()

        assert warnings
        assert page._actions[0] is block  # unchanged

    def test_wrap_inside_a_branch_works(self, page, monkeypatch):
        created = WhileBlock(condition=_cond())
        monkeypatch.setattr(bm.WhileBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.WhileBlockDialog, "result_action", lambda self: created)
        block = _if_block(then_actions=[ClickAction(x=1, y=1), ClickAction(x=5, y=5)])
        page._actions = [block]
        page._refresh_list()
        page._tree_item_at_path([0, "then", 0]).setSelected(True)
        page._tree_item_at_path([0, "then", 1]).setSelected(True)

        page._on_wrap_in_while()

        assert block.then_actions == [created]
        assert len(created.actions) == 2


class TestUngroup:
    def test_ungroup_if_splices_then_and_else_in_order(self, page):
        a, b = ClickAction(x=1, y=1), ClickAction(x=2, y=2)
        block = IfBlock(condition=_cond(), then_actions=[a], else_actions=[b])
        page._actions = [block]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

        page._on_ungroup()

        assert page._actions == [a, b]

    def test_ungroup_while_splices_body(self, page):
        a = ClickAction(x=1, y=1)
        page._actions = [WhileBlock(condition=_cond(), actions=[a])]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

        page._on_ungroup()

        assert page._actions == [a]


class TestEditOps:
    def test_edit_if_replaces_condition_preserves_bodies(self, page, monkeypatch):
        new_cond = _cond(image_file="ref_new.png", color_variation=99)
        monkeypatch.setattr(bm.IfBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.IfBlockDialog, "result_condition", lambda self: new_cond)
        # Avoid real ImageConditionWidget.load hitting the filesystem thumbnail:
        monkeypatch.setattr(bm.IfBlockDialog, "__init__", lambda self, existing=None, parent=None: bm.QDialog.__init__(self, parent))
        block = _if_block()
        original_then = block.then_actions
        page._actions = [block]
        page._refresh_list()

        page._on_edit_item(page._action_list.topLevelItem(0))

        assert block.condition is new_cond
        assert block.then_actions is original_then

    def test_edit_header_routes_to_parent_if(self, page, monkeypatch):
        new_cond = _cond(image_file="ref_new.png")
        monkeypatch.setattr(bm.IfBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.IfBlockDialog, "result_condition", lambda self: new_cond)
        monkeypatch.setattr(bm.IfBlockDialog, "__init__", lambda self, existing=None, parent=None: bm.QDialog.__init__(self, parent))
        block = _if_block()
        page._actions = [block]
        page._refresh_list()
        else_header = page._action_list.topLevelItem(0).child(1)

        page._on_edit_item(else_header)

        assert block.condition is new_cond

    def test_edit_while_updates_caps_in_place(self, page, monkeypatch):
        replacement = WhileBlock(
            condition=_cond(image_file="ref_new.png"),
            timeout_seconds=45,
            max_iterations=9,
            check_interval_ms=250,
        )
        monkeypatch.setattr(bm.WhileBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.WhileBlockDialog, "result_action", lambda self: replacement)
        monkeypatch.setattr(bm.WhileBlockDialog, "__init__", lambda self, existing=None, parent=None: bm.QDialog.__init__(self, parent))
        body_click = ClickAction(x=1, y=1)
        block = WhileBlock(condition=_cond(), actions=[body_click])
        page._actions = [block]
        page._refresh_list()

        page._on_edit_item(page._action_list.topLevelItem(0))

        assert page._actions[0] is block  # same object, edited in place
        assert block.actions == [body_click]
        assert block.timeout_seconds == 45
        assert block.max_iterations == 9
        assert block.check_interval_ms == 250
        assert block.condition.image_file == "ref_new.png"


class TestHeaderRowSafety:
    def test_remove_with_header_selected_is_noop(self, page):
        block = _if_block()
        page._actions = [block]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0).child(0))

        page._on_remove()

        assert page._actions == [block]

    def test_move_with_header_selected_is_noop(self, page):
        block = _if_block()
        other = ClickAction(x=9, y=9)
        page._actions = [block, other]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0).child(0))

        page._move(1)

        assert page._actions == [block, other]

    def test_duplicate_with_header_selected_is_noop(self, page):
        block = _if_block()
        page._actions = [block]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0).child(1))

        page._on_duplicate()

        assert page._actions == [block]


class TestDuplicate:
    def test_duplicate_if_block_reassigns_all_ids(self, page):
        inner_while = WhileBlock(condition=_cond(), actions=[ClickAction(x=3, y=3)])
        block = IfBlock(
            condition=_cond(),
            then_actions=[ClickAction(x=1, y=1), inner_while],
            else_actions=[ClickAction(x=2, y=2)],
        )
        page._actions = [block]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

        page._on_duplicate()

        clone = page._actions[1]
        assert isinstance(clone, IfBlock)

        def all_ids(item):
            ids = [item.id]
            from src.models.action import child_lists
            for _, body in child_lists(item):
                for child in body:
                    ids.extend(all_ids(child))
            return ids

        assert set(all_ids(block)).isdisjoint(all_ids(clone))
        assert len(clone.then_actions) == 2
        assert len(clone.else_actions) == 1


class TestDragDrop:
    def test_drag_step_from_then_to_else(self, page):
        moved = ClickAction(x=1, y=1)
        block = IfBlock(condition=_cond(), then_actions=[moved],
                        else_actions=[ClickAction(x=2, y=2)])
        page._actions = [block]
        page._refresh_list()

        if_item = page._action_list.topLevelItem(0)
        then_header, else_header = if_item.child(0), if_item.child(1)
        step_item = then_header.takeChild(0)
        else_header.addChild(step_item)

        page._on_tree_dropped()

        block = page._actions[0]
        assert block.then_actions == []
        assert len(block.else_actions) == 2
        assert block.else_actions[-1] is moved

    def test_drag_step_into_while_body(self, page):
        moved = ClickAction(x=9, y=9)
        while_block = WhileBlock(condition=_cond(), actions=[ClickAction(x=1, y=1)])
        page._actions = [while_block, moved]
        page._refresh_list()

        root = page._action_list
        step_item = root.takeTopLevelItem(1)
        root.topLevelItem(0).addChild(step_item)

        page._on_tree_dropped()

        assert len(page._actions) == 1
        assert page._actions[0].actions[-1] is moved

    def test_drag_whole_if_block_keeps_branches(self, page):
        block = _if_block()
        trailing = ClickAction(x=9, y=9)
        page._actions = [block, trailing]
        page._refresh_list()

        root = page._action_list
        if_item = root.takeTopLevelItem(0)
        root.insertTopLevelItem(1, if_item)

        page._on_tree_dropped()

        assert page._actions[0] is trailing
        moved_block = page._actions[1]
        assert isinstance(moved_block, IfBlock)
        assert len(moved_block.then_actions) == 1
        assert len(moved_block.else_actions) == 1


class TestUndo:
    def test_undo_reverts_wrap_in_if(self, page, monkeypatch):
        created = IfBlock(condition=_cond())
        monkeypatch.setattr(bm.IfBlockDialog, "exec", lambda self: bm.QDialog.Accepted)
        monkeypatch.setattr(bm.IfBlockDialog, "result_action", lambda self: created)
        a = ClickAction(x=1, y=1)
        page._actions = [a]
        page._refresh_list()
        page._action_list.topLevelItem(0).setSelected(True)

        page._on_wrap_in_if()
        assert isinstance(page._actions[0], IfBlock)

        page._on_undo()

        assert len(page._actions) == 1
        assert isinstance(page._actions[0], ClickAction)


class TestRoundTrip:
    def test_if_while_wait_macro_round_trips_through_json(self, page, macro_service, tmp_path):
        page._name_input.setText("Conditional")
        page._actions = [
            IfBlock(
                condition=_cond(),
                then_actions=[
                    WhileBlock(
                        condition=_cond(image_file="b.png"),
                        actions=[WaitAction(condition=_cond(image_file="c.png"))],
                        max_iterations=5,
                    ),
                ],
                else_actions=[LoopBlock(count=2, actions=[ClickAction(x=1, y=1)])],
            ),
        ]

        page._on_save()

        fresh = MacroService(tmp_path / "macros.json")
        macro = fresh.get_all()[0]
        block = macro.actions[0]
        assert isinstance(block, IfBlock)
        inner = block.then_actions[0]
        assert isinstance(inner, WhileBlock)
        assert inner.max_iterations == 5
        assert isinstance(inner.actions[0], WaitAction)
        assert inner.actions[0].condition.image_file == "c.png"
        assert isinstance(block.else_actions[0], LoopBlock)


class TestContextMenu:
    def test_header_row_only_allows_edit(self, page):
        page._actions = [_if_block()]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0).child(0))

        menu = page._build_context_menu()

        enabled = {a.text(): a.isEnabled() for a in menu.actions() if a.text()}
        assert enabled["Edit…"] is True
        assert enabled["Remove"] is False
        assert enabled["Duplicate"] is False
        assert enabled["Wrap in If…"] is False
        assert enabled["Ungroup block"] is False

    def test_block_row_enables_ungroup(self, page):
        page._actions = [WhileBlock(condition=_cond())]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

        menu = page._build_context_menu()

        enabled = {a.text(): a.isEnabled() for a in menu.actions() if a.text()}
        assert enabled["Ungroup block"] is True
        assert enabled["Wrap in While…"] is True

    def test_leaf_row_disables_ungroup(self, page):
        page._actions = [ClickAction(x=1, y=1)]
        page._refresh_list()
        page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

        menu = page._build_context_menu()

        enabled = {a.text(): a.isEnabled() for a in menu.actions() if a.text()}
        assert enabled["Ungroup block"] is False
        assert enabled["Remove"] is True


class TestRealisticMovement:
    def test_position_unknowable_after_conditional_block(self, page, monkeypatch):
        monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, False))
        page._actions = [
            ClickAction(x=10, y=10),
            IfBlock(condition=_cond(), then_actions=[ClickAction(x=99, y=99)]),
            ClickAction(x=10, y=10),
        ]

        page._on_realistic_movement()

        # After the If, the cursor position is unknown, so the trailing click
        # at (10,10) gets a fresh Move even though (10,10) was the last known
        # position before the block.
        from src.models.action import MouseMoveAction
        kinds = [type(a).__name__ for a in page._actions]
        assert kinds == ["MouseMoveAction", "ClickAction", "IfBlock", "MouseMoveAction", "ClickAction"]

    def test_moves_inserted_inside_branches(self, page, monkeypatch):
        monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, False))
        block = IfBlock(condition=_cond(), then_actions=[ClickAction(x=50, y=50)])
        page._actions = [ClickAction(x=10, y=10), block]

        page._on_realistic_movement()

        from src.models.action import MouseMoveAction
        assert isinstance(block.then_actions[0], MouseMoveAction)
        assert (block.then_actions[0].x, block.then_actions[0].y) == (50, 50)
