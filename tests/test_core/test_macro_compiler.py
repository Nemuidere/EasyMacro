"""
Tests for the macro compiler.

Pure-Python tests (no Qt event loop): assert the exact instruction shapes and
jump targets that if/while/loop structures compile into — the engine's
correctness rests on these indices being right.
"""

import pytest

from src.core.macro_compiler import CondJump, Jump, WhileHeader, compile_program
from src.models.action import (
    ClickAction,
    IfBlock,
    ImageCondition,
    LoopBlock,
    WhileBlock,
)


def _cond(**overrides) -> ImageCondition:
    fields = {"image_file": "ref_test.png", "x1": 0, "y1": 0, "x2": 10, "y2": 10}
    fields.update(overrides)
    return ImageCondition(**fields)


def _click(n: int) -> ClickAction:
    return ClickAction(x=n, y=n)


class TestLeafPassthrough:
    def test_plain_actions_pass_through_unchanged(self):
        actions = [_click(1), _click(2)]

        program = compile_program(actions)

        assert program == actions

    def test_loop_block_still_unrolls_statically(self):
        program = compile_program([LoopBlock(count=3, actions=[_click(1)])])

        assert len(program) == 3
        assert all(isinstance(i, ClickAction) for i in program)


class TestIfCompilation:
    def test_if_without_else(self):
        # [CondJump(->3), click, click]  — false jumps past the block
        block = IfBlock(condition=_cond(), then_actions=[_click(1), _click(2)])

        program = compile_program([block])

        assert isinstance(program[0], CondJump)
        assert program[0].target == 3
        assert len(program) == 3

    def test_if_with_else(self):
        # [CondJump(->3), then_click, Jump(->4), else_click]
        block = IfBlock(
            condition=_cond(),
            then_actions=[_click(1)],
            else_actions=[_click(2)],
        )

        program = compile_program([block])

        assert isinstance(program[0], CondJump)
        assert program[0].target == 3          # false -> start of else
        assert program[1].x == 1
        assert isinstance(program[2], Jump)
        assert program[2].target == 4          # end of then skips the else
        assert program[3].x == 2

    def test_empty_then_with_else(self):
        # [CondJump(->2), Jump(->3), else_click]
        block = IfBlock(condition=_cond(), else_actions=[_click(2)])

        program = compile_program([block])

        assert program[0].target == 2
        assert isinstance(program[1], Jump)
        assert program[1].target == 3

    def test_trailing_actions_after_if_get_correct_targets(self):
        block = IfBlock(condition=_cond(), then_actions=[_click(1)])

        program = compile_program([block, _click(9)])

        assert program[0].target == 2
        assert program[2].x == 9


class TestWhileCompilation:
    def test_while_shape(self):
        # [WhileHeader(exit->3), click, Jump(->0, delay=interval)]
        block = WhileBlock(condition=_cond(), actions=[_click(1)], check_interval_ms=250)

        program = compile_program([block])

        header = program[0]
        assert isinstance(header, WhileHeader)
        assert header.exit_target == 3
        back = program[2]
        assert isinstance(back, Jump)
        assert back.target == 0
        assert back.delay_ms == 250

    def test_while_caps_carried_onto_header(self):
        block = WhileBlock(condition=_cond(), max_iterations=7, timeout_seconds=30)

        program = compile_program([block])

        assert program[0].max_iterations == 7
        assert program[0].timeout_seconds == 30

    def test_empty_while_body_is_still_valid(self):
        # [WhileHeader(exit->2), Jump(->0)] — a busy-wait; the back-edge's
        # delay is what keeps it from hammering the screen search.
        block = WhileBlock(condition=_cond(), check_interval_ms=100)

        program = compile_program([block])

        assert program[0].exit_target == 2
        assert program[1].target == 0
        assert program[1].delay_ms == 100

    def test_negated_condition_preserved(self):
        block = WhileBlock(condition=_cond(negate=True))

        program = compile_program([block])

        assert program[0].condition.negate is True


class TestNestedCompilation:
    def test_while_inside_loop_gets_fresh_copies_with_consistent_targets(self):
        # Each unrolled copy of the while must jump within ITSELF, not into
        # another copy — this is what makes index-keyed runtime state safe.
        inner = WhileBlock(condition=_cond(), actions=[_click(1)])
        program = compile_program([LoopBlock(count=2, actions=[inner])])

        # copy 1: [0]=header(exit->3) [1]=click [2]=Jump(->0)
        # copy 2: [3]=header(exit->6) [4]=click [5]=Jump(->3)
        assert len(program) == 6
        assert isinstance(program[0], WhileHeader) and program[0].exit_target == 3
        assert isinstance(program[2], Jump) and program[2].target == 0
        assert isinstance(program[3], WhileHeader) and program[3].exit_target == 6
        assert isinstance(program[5], Jump) and program[5].target == 3
        # The two headers must be distinct objects (separate runtime state).
        assert program[0] is not program[3]

    def test_if_inside_while(self):
        block = WhileBlock(
            condition=_cond(),
            actions=[IfBlock(condition=_cond(), then_actions=[_click(1)])],
        )

        program = compile_program([block])

        # [0]=WhileHeader(exit->4) [1]=CondJump(->3) [2]=click [3]=Jump(->0)
        assert program[0].exit_target == 4
        assert isinstance(program[1], CondJump) and program[1].target == 3
        assert isinstance(program[3], Jump) and program[3].target == 0
