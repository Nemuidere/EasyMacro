"""
Macro service for EasyMacro.

Provides business logic for macro management including CRUD operations
and persistence.
"""

from typing import Optional, List
from pathlib import Path
import json

from src.models.macro import Macro, MacroStatus
from src.models.action import Action
from src.core.config import ConfigManager
from src.core.exceptions import MacroError, MacroNotFoundError
from src.core.logger import get_logger
from src.core.event_bus import EventBus, get_event_bus


class MacroService:
    """
    Service for managing macros.
    
    Handles CRUD operations, persistence, and business logic for macros.
    
    Usage:
        service = MacroService(Path("data/macros.json"))
        service.save(macro)
        macro = service.get("macro_id")
        all_macros = service.get_all()
    """
    
    def __init__(self, macros_path: Path):
        """Initialize macro service.
        
        Args:
            macros_path: Path to the macros JSON file.
        
        Raises:
            ValueError: If macros_path is None.
        """
        if macros_path is None:
            raise ValueError("Macros path cannot be None")
        
        self._macros_path = macros_path
        self._macros: dict[str, Macro] = {}
        self._logger = get_logger("macro_service")
        self._event_bus = get_event_bus()
        
        self._ensure_file_exists()
        self._load_all()
    
    def _ensure_file_exists(self) -> None:
        """Ensure the macros file exists."""
        if not self._macros_path.exists():
            self._macros_path.parent.mkdir(parents=True, exist_ok=True)
            self._macros_path.write_text("[]")
    
    def _load_all(self) -> None:
        """Load all macros from the JSON file."""
        try:
            content = self._macros_path.read_text()
            if not content.strip():
                self._macros = {}
                return
            
            data = json.loads(content)
            self._macros = {
                macro_data["id"]: Macro.model_validate(macro_data)
                for macro_data in data
            }
            
            self._logger.info(f"Loaded {len(self._macros)} macros")
            
        except Exception as e:
            self._logger.error(f"Failed to load macros: {e}")
            self._macros = {}
    
    def _save_all(self) -> None:
        """Save all macros to the JSON file."""
        try:
            data = [macro.model_dump() for macro in self._macros.values()]
            self._macros_path.write_text(
                json.dumps(data, indent=2, default=str)
            )
            self._logger.debug(f"Saved {len(self._macros)} macros")
            
        except Exception as e:
            self._logger.error(f"Failed to save macros: {e}")
            raise MacroError(f"Failed to save macros: {e}") from e
    
    def get(self, macro_id: str) -> Macro:
        """Get a macro by ID.
        
        Args:
            macro_id: ID of the macro to get.
        
        Returns:
            The macro with the given ID.
        
        Raises:
            ValueError: If macro_id is empty.
            MacroNotFoundError: If macro not found.
        """
        if not macro_id:
            raise ValueError("Macro ID cannot be empty")
        
        if macro_id not in self._macros:
            raise MacroNotFoundError(f"Macro not found: {macro_id}")
        
        return self._macros[macro_id]
    
    def get_all(self) -> List[Macro]:
        """Get all macros.
        
        Returns:
            List of all macros.
        """
        return list(self._macros.values())
    
    def get_enabled(self) -> List[Macro]:
        """Get all enabled macros.
        
        Returns:
            List of enabled macros.
        """
        return [m for m in self._macros.values() if m.enabled]
    
    def save(self, macro: Macro) -> None:
        """Save a macro.
        
        Creates a new macro if it doesn't exist, updates otherwise.
        
        Args:
            macro: Macro to save.
        
        Raises:
            ValueError: If macro is None.
        """
        if macro is None:
            raise ValueError("Macro cannot be None")

        is_new = macro.id not in self._macros
        self._macros[macro.id] = macro
        self._save_all()

        if is_new:
            self._logger.info(f"Created macro: {macro.name}")
        else:
            self._logger.info(f"Updated macro: {macro.name}")

        # Emit signal after successful save
        if self._event_bus is not None:
            self._event_bus.macro_saved.emit(macro)

        # Register/unregister hotkey if changed
        try:
            from src.services.macro_hotkey_service import get_macro_hotkey_service
            macro_hotkey_service = get_macro_hotkey_service()

            # Get old macro to check if hotkey changed
            old_macro = self._macros.get(macro.id)
            old_hotkey = old_macro.hotkey if old_macro else None

            if macro.hotkey != old_hotkey:
                # Unregister old hotkey if exists
                if old_hotkey:
                    macro_hotkey_service.unregister_macro_hotkey(macro.id)

                # Register new hotkey if exists
                if macro.hotkey and macro.enabled:
                    from typing import Callable
                    def make_callback(m: Macro) -> Callable[[], None]:
                        def callback():
                            macro_hotkey_service._on_macro_hotkey_pressed(m.id)
                        return callback
                    macro_hotkey_service.register_macro_hotkey(macro, make_callback(macro))
        except RuntimeError:
            pass  # MacroHotkeyService not initialized
    
    def delete(self, macro_id: str) -> None:
        """Delete a macro.
        
        Args:
            macro_id: ID of the macro to delete.
        
        Raises:
            ValueError: If macro_id is empty.
            MacroNotFoundError: If macro not found.
        """
        if not macro_id:
            raise ValueError("Macro ID cannot be empty")
        
        if macro_id not in self._macros:
            raise MacroNotFoundError(f"Macro not found: {macro_id}")

        macro = self._macros.pop(macro_id)
        self._save_all()

        self._logger.info(f"Deleted macro: {macro.name}")

        # Unregister hotkey
        try:
            from src.services.macro_hotkey_service import get_macro_hotkey_service
            macro_hotkey_service = get_macro_hotkey_service()
            macro_hotkey_service.unregister_macro_hotkey(macro_id)
        except RuntimeError:
            pass  # MacroHotkeyService not initialized
    
    def exists(self, macro_id: str) -> bool:
        """Check if a macro exists.
        
        Args:
            macro_id: ID of the macro to check.
        
        Returns:
            True if exists, False otherwise.
        """
        return macro_id in self._macros
    
    def count(self) -> int:
        """Get the total number of macros.
        
        Returns:
            Number of macros.
        """
        return len(self._macros)
    
    def clear(self) -> None:
        """Delete all macros."""
        self._macros.clear()
        self._save_all()
        self._logger.info("Cleared all macros")
    
    def find_by_name(self, name: str) -> Optional[Macro]:
        """Find a macro by name.
        
        Args:
            name: Name to search for.
        
        Returns:
            Macro if found, None otherwise.
        
        Raises:
            ValueError: If name is empty.
        """
        if not name:
            raise ValueError("Name cannot be empty")
        
        for macro in self._macros.values():
            if macro.name.lower() == name.lower():
                return macro
        
        return None
    
    def find_by_hotkey(self, hotkey: str) -> Optional[Macro]:
        """Find a macro by hotkey.
        
        Args:
            hotkey: Hotkey to search for.
        
        Returns:
            Macro if found, None otherwise.
        
        Raises:
            ValueError: If hotkey is empty.
        """
        if not hotkey:
            raise ValueError("Hotkey cannot be empty")
        
        hotkey = hotkey.lower().strip()
        
        for macro in self._macros.values():
            if macro.hotkey and macro.hotkey.lower() == hotkey:
                return macro
        
        return None


# Global singleton instance
_macro_service: Optional[MacroService] = None


def get_macro_service() -> MacroService:
    """Get the global macro service instance.
    
    Raises:
        RuntimeError: If service not initialized.
    
    Returns:
        MacroService: The global service instance.
    """
    if _macro_service is None:
        raise RuntimeError(
            "Macro service not initialized. "
            "Call init_macro_service() first."
        )
    return _macro_service


def init_macro_service(macros_path: Path) -> MacroService:
    """Initialize the global macro service.
    
    Args:
        macros_path: Path to the macros JSON file.
    
    Returns:
        MacroService: The newly created service instance.
    
    Raises:
        RuntimeError: If service already initialized.
        ValueError: If macros_path is None.
    """
    global _macro_service
    if _macro_service is not None:
        raise RuntimeError("Macro service already initialized.")
    _macro_service = MacroService(macros_path)
    return _macro_service
