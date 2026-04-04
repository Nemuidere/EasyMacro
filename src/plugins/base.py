"""
Plugin base class for EasyMacro.

Defines the interface that all plugins must implement.
"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class PluginMetadata(BaseModel):
    """Plugin metadata containing identification and configuration."""
    
    name: str
    version: str
    author: str
    description: str = ""
    enabled: bool = True


class PluginBase(ABC):
    """
    Abstract base class for all EasyMacro plugins.
    
    Plugins can hook into macro execution lifecycle events and extend
    EasyMacro's functionality. All plugins must inherit from this class.
    
    Lifecycle:
        1. Plugin is discovered by PluginManager
        2. on_load() is called when plugin is loaded
        3. Plugin can hook into events (on_macro_start, on_action, etc.)
        4. on_unload() is called when plugin is unloaded
    
    Example:
        class MyPlugin(PluginBase):
            name = "My Plugin"
            version = "1.0.0"
            
            def on_load(self) -> None:
                print(f"{self.name} loaded!")
            
            def on_macro_start(self, macro_id: str) -> None:
                print(f"Macro {macro_id} started")
    """
    
    # Plugin metadata (must be overridden by subclasses)
    name: str = "Unnamed Plugin"
    version: str = "0.0.0"
    author: str = "Unknown"
    description: str = ""
    
    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata.
        
        Returns:
            PluginMetadata containing plugin information.
        """
        return PluginMetadata(
            name=self.name,
            version=self.version,
            author=self.author,
            description=self.description
        )
    
    # Lifecycle hooks
    
    @abstractmethod
    def on_load(self) -> None:
        """Called when the plugin is loaded.
        
        Override this method to initialize plugin resources.
        This is called once when the plugin is first loaded.
        
        Raises:
            PluginLoadError: If plugin fails to initialize.
        """
        pass
    
    @abstractmethod
    def on_unload(self) -> None:
        """Called when the plugin is unloaded.
        
        Override this method to clean up plugin resources.
        This is called once when the plugin is being unloaded.
        """
        pass
    
    # Optional event hooks
    
    def on_macro_start(self, macro_id: str) -> None:
        """Called when a macro starts execution.
        
        Args:
            macro_id: ID of the macro that started.
        """
        pass
    
    def on_macro_end(self, macro_id: str) -> None:
        """Called when a macro finishes execution.
        
        Args:
            macro_id: ID of the macro that finished.
        """
        pass
    
    def on_macro_error(self, macro_id: str, error: str) -> None:
        """Called when a macro encounters an error.
        
        Args:
            macro_id: ID of the macro that errored.
            error: Error message.
        """
        pass
    
    def on_action(self, macro_id: str, action_type: str, action_data: dict[str, Any]) -> None:
        """Called before each action in a macro.
        
        Args:
            macro_id: ID of the macro.
            action_type: Type of action (e.g., "click", "delay").
            action_data: Action parameters.
        """
        pass
    
    def on_hotkey_triggered(self, hotkey: str) -> None:
        """Called when a hotkey is triggered.
        
        Args:
            hotkey: The hotkey combination that was triggered.
        """
        pass
    
    def on_settings_changed(self, key: str, value: Any) -> None:
        """Called when application settings change.
        
        Args:
            key: Setting key that changed.
            value: New value.
        """
        pass
    
    def __repr__(self) -> str:
        """String representation of the plugin."""
        return f"{self.__class__.__name__}(name={self.name!r}, version={self.version!r})"
