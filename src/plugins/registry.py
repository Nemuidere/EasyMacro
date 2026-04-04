"""
Plugin registry for EasyMacro.

Tracks available plugins and their metadata.
"""

from typing import Dict, Optional
from pathlib import Path

from src.plugins.base import PluginMetadata
from src.core.exceptions import PluginLoadError


class PluginRegistry:
    """
    Registry for tracking available plugins.
    
    Stores metadata about plugins without loading them.
    Used for plugin discovery and marketplace functionality.
    
    Usage:
        registry = PluginRegistry()
        registry.register("MyPlugin", metadata, Path("plugins/my_plugin.py"))
        metadata = registry.get_metadata("MyPlugin")
    """
    
    def __init__(self):
        """Initialize plugin registry."""
        self._registry: Dict[str, tuple[PluginMetadata, Path]] = {}
    
    def register(self, name: str, metadata: PluginMetadata, path: Path) -> None:
        """Register a plugin.
        
        Args:
            name: Plugin name.
            metadata: Plugin metadata.
            path: Path to plugin file.
        
        Raises:
            ValueError: If name is empty or metadata is None.
        """
        if not name:
            raise ValueError("Plugin name cannot be empty")
        if metadata is None:
            raise ValueError("Plugin metadata cannot be None")
        
        self._registry[name] = (metadata, path)
    
    def unregister(self, name: str) -> None:
        """Unregister a plugin.
        
        Args:
            name: Plugin name.
        
        Raises:
            PluginLoadError: If plugin not found.
        """
        if name not in self._registry:
            raise PluginLoadError(f"Plugin not registered: {name}")
        
        del self._registry[name]
    
    def get_metadata(self, name: str) -> Optional[PluginMetadata]:
        """Get metadata for a registered plugin.
        
        Args:
            name: Plugin name.
        
        Returns:
            Plugin metadata, or None if not found.
        """
        entry = self._registry.get(name)
        if entry is None:
            return None
        return entry[0]
    
    def get_path(self, name: str) -> Optional[Path]:
        """Get path for a registered plugin.
        
        Args:
            name: Plugin name.
        
        Returns:
            Plugin path, or None if not found.
        """
        entry = self._registry.get(name)
        if entry is None:
            return None
        return entry[1]
    
    def is_registered(self, name: str) -> bool:
        """Check if a plugin is registered.
        
        Args:
            name: Plugin name.
        
        Returns:
            True if registered, False otherwise.
        """
        return name in self._registry
    
    def get_all(self) -> Dict[str, PluginMetadata]:
        """Get all registered plugins.
        
        Returns:
            Dictionary of plugin names to metadata.
        """
        return {name: metadata for name, (metadata, _) in self._registry.items()}
