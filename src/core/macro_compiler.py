"""
Macro compiler for EasyMacro.

Lowers a macro's item tree (leaf actions plus Loop/If/While blocks) into a
flat instruction list the engine can walk with a single integer instruction
pointer. Fixed-count LoopBlocks are still statically unrolled (same semantics
as the old ``flatten_items``); If/While blocks — whose branch/iteration counts
depend on a runtime screen condition — compile into conditional-jump
instructions instead.

Keeping the program flat and the instruction pointer a single int is what
lets the engine's pause/resume/stop/repeat-wrap logic stay untouched.

This module is pure Python (no Qt) so it can be tested without an event loop.
"""

from dataclasses import dataclass

from src.models.action import IfBlock, ImageCondition, LoopBlock, WhileBlock


@dataclass
class Jump:
    """Unconditionally move the instruction pointer to ``target``.

    Attributes:
        target: Instruction index to jump to.
        delay_ms: Delay before the jump lands. A while-loop's back-edge
            carries the block's check_interval_ms here so a fast/empty body
            can't re-run the screen search in a tight loop.
    """

    target: int
    delay_ms: int = 0


@dataclass
class CondJump:
    """Evaluate a condition; fall through if true, jump to ``target`` if false.

    Compiled from an IfBlock's header: ``target`` is the else-branch (or the
    end of the block when there is no else).

    Attributes:
        condition: The screen condition to evaluate.
        target: Instruction index to jump to when the condition is false.
        block_id: The owning IfBlock's model id (logging only).
    """

    condition: ImageCondition
    target: int
    block_id: str


@dataclass
class WhileHeader:
    """A while-loop's condition check, run before every pass.

    Falls through into the body while the condition holds and no cap is hit;
    jumps to ``exit_target`` otherwise. The engine keys this instruction's
    runtime state (iteration count, start time) by its instruction index —
    correct because LoopBlock unrolling emits each copy at its own index.

    Attributes:
        condition: The screen condition to evaluate.
        exit_target: Instruction index just past the loop's back-edge.
        block_id: The owning WhileBlock's model id (logging only).
        max_iterations: Stop after this many passes (0 = unlimited).
        timeout_seconds: Stop this long after the first check (0 = unlimited).
    """

    condition: ImageCondition
    exit_target: int
    block_id: str
    max_iterations: int = 0
    timeout_seconds: int = 0


def compile_program(items: list) -> list:
    """Compile a macro's item tree into a flat instruction list.

    Args:
        items: A list of MacroItems (leaf actions and/or blocks).

    Returns:
        A flat list where each element is either a leaf Action (executed
        as-is) or a Jump/CondJump/WhileHeader control instruction.
    """
    program: list = []
    _emit(items, program)
    return program


def _emit(items: list, program: list) -> None:
    """Recursively append instructions for ``items`` to ``program``."""
    for item in items:
        if isinstance(item, LoopBlock):
            # Static unroll, emitting the body FRESH each iteration: jump
            # targets are absolute indices, so every copy of a nested
            # While/If needs its own instructions (and thereby its own
            # runtime-state key in the engine).
            for _ in range(item.count):
                _emit(item.actions, program)
        elif isinstance(item, IfBlock):
            header = CondJump(condition=item.condition, target=-1, block_id=item.id)
            program.append(header)
            _emit(item.then_actions, program)
            if item.else_actions:
                skip_else = Jump(target=-1)
                program.append(skip_else)
                header.target = len(program)
                _emit(item.else_actions, program)
                skip_else.target = len(program)
            else:
                header.target = len(program)
        elif isinstance(item, WhileBlock):
            header_index = len(program)
            header = WhileHeader(
                condition=item.condition,
                exit_target=-1,
                block_id=item.id,
                max_iterations=item.max_iterations,
                timeout_seconds=item.timeout_seconds,
            )
            program.append(header)
            _emit(item.actions, program)
            program.append(Jump(target=header_index, delay_ms=item.check_interval_ms))
            header.exit_target = len(program)
        else:
            program.append(item)
