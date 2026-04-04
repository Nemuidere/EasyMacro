"""
Tests for MacroService.

Tests CRUD operations and persistence.
"""

import pytest
import json

from src.services.macro_service import MacroService, init_macro_service, get_macro_service
from src.models.macro import Macro, MacroStatus
from src.models.action import ClickAction, DelayAction
from src.core.exceptions import MacroNotFoundError


class TestMacroService:
    """Tests for MacroService class."""
    
    def test_init_creates_file(self, temp_macros_file):
        """Test that initialization creates the file if it doesn't exist."""
        # Delete the file
        temp_macros_file.unlink()
        
        MacroService(temp_macros_file)
        
        assert temp_macros_file.exists()
    
    def test_init_with_none_raises_error(self):
        """Test that initialization with None raises ValueError."""
        with pytest.raises(ValueError, match="Macros path cannot be None"):
            MacroService(None)
    
    def test_save_and_get_macro(self, temp_macros_file, sample_macro):
        """Test saving and retrieving a macro."""
        service = MacroService(temp_macros_file)
        
        service.save(sample_macro)
        
        retrieved = service.get(sample_macro.id)
        
        assert retrieved.id == sample_macro.id
        assert retrieved.name == sample_macro.name
    
    def test_get_nonexistent_macro_raises_error(self, temp_macros_file):
        """Test that getting nonexistent macro raises MacroNotFoundError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(MacroNotFoundError, match="Macro not found"):
            service.get("nonexistent_id")
    
    def test_get_with_empty_id_raises_error(self, temp_macros_file):
        """Test that getting with empty ID raises ValueError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(ValueError, match="Macro ID cannot be empty"):
            service.get("")
    
    def test_get_all_returns_list(self, temp_macros_file, sample_macro):
        """Test that get_all returns a list."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        macros = service.get_all()
        
        assert isinstance(macros, list)
        assert len(macros) == 1
    
    def test_get_enabled_returns_only_enabled(self, temp_macros_file):
        """Test that get_enabled returns only enabled macros."""
        service = MacroService(temp_macros_file)
        
        enabled_macro = Macro(name="Enabled", enabled=True)
        disabled_macro = Macro(name="Disabled", enabled=False)
        
        service.save(enabled_macro)
        service.save(disabled_macro)
        
        enabled = service.get_enabled()
        
        assert len(enabled) == 1
        assert enabled[0].name == "Enabled"
    
    def test_save_with_none_raises_error(self, temp_macros_file):
        """Test that saving None raises ValueError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(ValueError, match="Macro cannot be None"):
            service.save(None)
    
    def test_delete_macro(self, temp_macros_file, sample_macro):
        """Test deleting a macro."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        service.delete(sample_macro.id)
        
        with pytest.raises(MacroNotFoundError):
            service.get(sample_macro.id)
    
    def test_delete_nonexistent_raises_error(self, temp_macros_file):
        """Test that deleting nonexistent macro raises MacroNotFoundError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(MacroNotFoundError, match="Macro not found"):
            service.delete("nonexistent_id")
    
    def test_delete_with_empty_id_raises_error(self, temp_macros_file):
        """Test that deleting with empty ID raises ValueError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(ValueError, match="Macro ID cannot be empty"):
            service.delete("")
    
    def test_exists(self, temp_macros_file, sample_macro):
        """Test checking if macro exists."""
        service = MacroService(temp_macros_file)
        
        assert service.exists(sample_macro.id) is False
        
        service.save(sample_macro)
        
        assert service.exists(sample_macro.id) is True
    
    def test_count(self, temp_macros_file):
        """Test counting macros."""
        service = MacroService(temp_macros_file)
        
        assert service.count() == 0
        
        service.save(Macro(name="Macro 1"))
        service.save(Macro(name="Macro 2"))
        
        assert service.count() == 2
    
    def test_clear(self, temp_macros_file, sample_macro):
        """Test clearing all macros."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        service.clear()
        
        assert service.count() == 0
    
    def test_find_by_name(self, temp_macros_file, sample_macro):
        """Test finding macro by name."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        found = service.find_by_name("Test Macro")
        
        assert found is not None
        assert found.id == sample_macro.id
    
    def test_find_by_name_case_insensitive(self, temp_macros_file, sample_macro):
        """Test finding macro by name is case insensitive."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        found = service.find_by_name("test macro")
        
        assert found is not None
    
    def test_find_by_name_not_found(self, temp_macros_file):
        """Test finding macro by name returns None if not found."""
        service = MacroService(temp_macros_file)
        
        found = service.find_by_name("Nonexistent")
        
        assert found is None
    
    def test_find_by_name_with_empty_raises_error(self, temp_macros_file):
        """Test that finding with empty name raises ValueError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(ValueError, match="Name cannot be empty"):
            service.find_by_name("")
    
    def test_find_by_hotkey(self, temp_macros_file, sample_macro):
        """Test finding macro by hotkey."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        found = service.find_by_hotkey("ctrl+shift+a")
        
        assert found is not None
        assert found.id == sample_macro.id
    
    def test_find_by_hotkey_case_insensitive(self, temp_macros_file, sample_macro):
        """Test finding macro by hotkey is case insensitive."""
        service = MacroService(temp_macros_file)
        service.save(sample_macro)
        
        found = service.find_by_hotkey("CTRL+SHIFT+A")
        
        assert found is not None
    
    def test_find_by_hotkey_not_found(self, temp_macros_file):
        """Test finding macro by hotkey returns None if not found."""
        service = MacroService(temp_macros_file)
        
        found = service.find_by_hotkey("ctrl+a")
        
        assert found is None
    
    def test_find_by_hotkey_with_empty_raises_error(self, temp_macros_file):
        """Test that finding with empty hotkey raises ValueError."""
        service = MacroService(temp_macros_file)
        
        with pytest.raises(ValueError, match="Hotkey cannot be empty"):
            service.find_by_hotkey("")


class TestMacroServiceSingleton:
    """Tests for singleton functions."""
    
    def test_init_macro_service(self, temp_macros_file):
        """Test initializing the singleton."""
        # Reset singleton
        import src.services.macro_service as ms_module
        ms_module._macro_service = None
        
        service = init_macro_service(temp_macros_file)
        
        assert service is not None
        assert isinstance(service, MacroService)
        
        # Cleanup
        ms_module._macro_service = None
    
    def test_init_twice_raises_error(self, temp_macros_file):
        """Test that initializing twice raises RuntimeError."""
        # Reset singleton
        import src.services.macro_service as ms_module
        ms_module._macro_service = None
        
        init_macro_service(temp_macros_file)
        
        with pytest.raises(RuntimeError, match="already initialized"):
            init_macro_service(temp_macros_file)
        
        # Cleanup
        ms_module._macro_service = None
    
    def test_get_without_init_raises_error(self):
        """Test that getting without init raises RuntimeError."""
        # Reset singleton
        import src.services.macro_service as ms_module
        ms_module._macro_service = None
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_macro_service()
