"""
AHK Service for EasyMacro.

Provides integration with AutoHotkey via python-ahk library.

Dependencies:
    python-ahk is required. Install with:
        pip install ahk[binary]

    For more information, see: https://github.com/spyoungtech/ahk
"""

from typing import Optional, Tuple
from pathlib import Path

from ahk import AHK

from src.core.exceptions import MacroExecutionError
from src.core.logger import get_logger


class AHKService:
    """
    Service for interacting with AutoHotkey.
    
    Provides mouse and keyboard control via python-ahk.
    
    Usage:
        service = AHKService()
        service.click(100, 200)
        service.key_press("a", modifiers=["ctrl"])
    """
    
    def __init__(self):
        """Initialize AHK service."""
        self._logger = get_logger("ahk_service")
        self._ahk = AHK()
        self._logger.info("AHK service initialized successfully")
    
    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_count: int = 1
    ) -> None:
        """Perform a mouse click at the specified position.
        
        Args:
            x: X coordinate.
            y: Y coordinate.
            button: Mouse button ("left", "right", "middle").
            click_count: Number of clicks.
        
        Raises:
            ValueError: If coordinates are negative.
            MacroExecutionError: If click fails.
        """
        if x < 0:
            raise ValueError(f"X coordinate cannot be negative: {x}")
        if y < 0:
            raise ValueError(f"Y coordinate cannot be negative: {y}")
        
        self._logger.debug(f"Click at ({x}, {y}) with button {button}")
        
        try:
            # Move to position
            self._ahk.mouse_move(x, y, speed=0)
            
            # Perform click
            if button == "left":
                for _ in range(click_count):
                    self._ahk.left_click()
            elif button == "right":
                for _ in range(click_count):
                    self._ahk.right_click()
            elif button == "middle":
                for _ in range(click_count):
                    self._ahk.middle_click()
            else:
                raise ValueError(f"Unknown button: {button}")
                
        except Exception as e:
            self._logger.error(f"Click failed: {e}")
            raise MacroExecutionError(f"Click failed: {e}") from e
    
    def mouse_move(
        self,
        x: int,
        y: int,
        speed: int = 5,
        smooth: bool = True
    ) -> None:
        """Move the mouse to a position.
        
        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            speed: Movement speed (1-10).
            smooth: Whether to use smooth movement.
        
        Raises:
            ValueError: If coordinates are negative or speed out of range.
            MacroExecutionError: If move fails.
        """
        if x < 0:
            raise ValueError(f"X coordinate cannot be negative: {x}")
        if y < 0:
            raise ValueError(f"Y coordinate cannot be negative: {y}")
        if not (1 <= speed <= 10):
            raise ValueError(f"Speed must be between 1 and 10: {speed}")
        
        self._logger.debug(f"Mouse move to ({x}, {y}) with speed {speed}")
        
        try:
            if smooth:
                self._ahk.mouse_move(x, y, speed=speed)
            else:
                self._ahk.mouse_move(x, y, speed=0)
                
        except Exception as e:
            self._logger.error(f"Mouse move failed: {e}")
            raise MacroExecutionError(f"Mouse move failed: {e}") from e
    
    def key_press(self, key: str, modifiers: Optional[list[str]] = None) -> None:
        """Press a key with optional modifiers.
        
        Args:
            key: Key to press.
            modifiers: Modifier keys ("ctrl", "alt", "shift", "meta").
        
        Raises:
            ValueError: If key is empty.
            MacroExecutionError: If key press fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        
        modifiers = modifiers or []
        self._logger.debug(f"Key press: {key} with modifiers {modifiers}")
        
        try:
            # Press modifiers
            for mod in modifiers:
                self._key_down(mod)
            
            # Press key
            self._ahk.key_press(key)
            
            # Release modifiers (in reverse order)
            for mod in reversed(modifiers):
                self._key_up(mod)
                
        except Exception as e:
            self._logger.error(f"Key press failed: {e}")
            raise MacroExecutionError(f"Key press failed: {e}") from e
    
    def key_down(self, key: str) -> None:
        """Hold a key down.
        
        Args:
            key: Key to hold.
        
        Raises:
            ValueError: If key is empty.
            MacroExecutionError: If key down fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        
        try:
            self._key_down(key)
        except Exception as e:
            raise MacroExecutionError(f"Key down failed: {e}") from e
    
    def key_up(self, key: str) -> None:
        """Release a key.
        
        Args:
            key: Key to release.
        
        Raises:
            ValueError: If key is empty.
            MacroExecutionError: If key up fails.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        
        try:
            self._key_up(key)
        except Exception as e:
            raise MacroExecutionError(f"Key up failed: {e}") from e
    
    def _key_down(self, key: str) -> None:
        """Internal method to hold a key down.
        
        Args:
            key: Key to hold.
        """
        self._ahk.key_down(key)
    
    def _key_up(self, key: str) -> None:
        """Internal method to release a key.
        
        Args:
            key: Key to release.
        """
        self._ahk.key_up(key)
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position.
        
        Returns:
            Tuple of (x, y) coordinates.
        
        Raises:
            MacroExecutionError: If getting position fails.
        """
        try:
            pos = self._ahk.mouse_position
            return (pos.x, pos.y)
        except Exception as e:
            raise MacroExecutionError(f"Failed to get mouse position: {e}") from e
    
    def sleep(self, milliseconds: int) -> None:
        """Sleep for a specified duration.
        
        Args:
            milliseconds: Duration in milliseconds.
        
        Raises:
            ValueError: If duration is negative.
        """
        if milliseconds < 0:
            raise ValueError(f"Duration cannot be negative: {milliseconds}")
        
        self._ahk.sleep(milliseconds)


# Global singleton instance
_ahk_service: Optional[AHKService] = None


def get_ahk_service() -> AHKService:
    """Get the global AHK service instance.
    
    Raises:
        RuntimeError: If service not initialized.
    
    Returns:
        AHKService: The global service instance.
    """
    if _ahk_service is None:
        raise RuntimeError(
            "AHK service not initialized. "
            "Call init_ahk_service() first."
        )
    return _ahk_service


def init_ahk_service() -> AHKService:
    """Initialize the global AHK service.
    
    Returns:
        AHKService: The newly created service instance.
    
    Raises:
        RuntimeError: If service already initialized.
    """
    global _ahk_service
    if _ahk_service is not None:
        raise RuntimeError("AHK service already initialized.")
    _ahk_service = AHKService()
    return _ahk_service
