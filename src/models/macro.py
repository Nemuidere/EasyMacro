"""
Macro models for EasyMacro.

Defines the macro data structure and related models.
"""

from enum import Enum
from typing import Optional
from pydantic import Field, field_validator

from src.models.base import EasyMacroBaseModel
from src.models.action import Action


class MacroStatus(str, Enum):
    """Status of a macro."""
    
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class Macro(EasyMacroBaseModel):
    """
    Macro definition.
    
    A macro is a sequence of actions that can be executed
    with optional randomization for human-like behavior.
    
    Attributes:
        name: Display name of the macro.
        description: Optional description.
        actions: List of actions to execute.
        hotkey: Optional hotkey to trigger the macro.
        enabled: Whether the macro is active.
        repeat_count: Number of times to repeat (0 = infinite).
        repeat_delay_ms: Delay between repetitions.
        randomization_enabled: Whether to apply randomization.
        status: Current execution status.
    """
    
    name: str = Field(min_length=1, max_length=100, description="Macro name")
    description: str = Field(default="", max_length=500, description="Macro description")
    actions: list[Action] = Field(default_factory=list, description="List of actions")
    hotkey: Optional[str] = Field(default=None, description="Hotkey to trigger macro")
    enabled: bool = Field(default=True, description="Whether macro is active")
    repeat_count: int = Field(default=1, ge=0, description="Repeat count (0 = infinite)")
    repeat_delay_ms: int = Field(default=0, ge=0, description="Delay between repetitions")
    randomization_enabled: bool = Field(default=True, description="Apply randomization")
    status: MacroStatus = Field(default=MacroStatus.IDLE, description="Current status")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate macro name.
        
        Args:
            v: Name to validate.
        
        Returns:
            Validated name (stripped).
        
        Raises:
            ValueError: If name is empty after stripping.
        """
        if not v or not v.strip():
            raise ValueError("Macro name cannot be empty")
        return v.strip()
    
    @field_validator("hotkey")
    @classmethod
    def validate_hotkey(cls, v: Optional[str]) -> Optional[str]:
        """Validate hotkey format.
        
        Args:
            v: Hotkey to validate.
        
        Returns:
            Validated hotkey (normalized).
        
        Raises:
            ValueError: If hotkey format is invalid.
        """
        if v is None:
            return None
        
        v = v.strip().lower()
        if not v:
            return None
        
        # Basic validation - hotkey should contain at least one key
        # Format: "ctrl+shift+a", "f1", "ctrl+1", etc.
        parts = v.split("+")
        if not parts:
            raise ValueError(f"Invalid hotkey format: {v}")
        
        return v
    
    def add_action(self, action: Action) -> None:
        """Add an action to the macro.
        
        Args:
            action: Action to add.
        """
        self.actions.append(action)
        self.touch()
    
    def remove_action(self, action_id: str) -> bool:
        """Remove an action from the macro.
        
        Args:
            action_id: ID of action to remove.
        
        Returns:
            True if action was removed, False if not found.
        """
        for i, action in enumerate(self.actions):
            if action.id == action_id:
                self.actions.pop(i)
                self.touch()
                return True
        return False
    
    def clear_actions(self) -> None:
        """Remove all actions from the macro."""
        self.actions.clear()
        self.touch()
    
    def is_running(self) -> bool:
        """Check if macro is currently running.
        
        Returns:
            True if running, False otherwise.
        """
        return self.status == MacroStatus.RUNNING
    
    def is_paused(self) -> bool:
        """Check if macro is currently paused.
        
        Returns:
            True if paused, False otherwise.
        """
        return self.status == MacroStatus.PAUSED
    
    def is_idle(self) -> bool:
        """Check if macro is idle.
        
        Returns:
            True if idle, False otherwise.
        """
        return self.status == MacroStatus.IDLE
