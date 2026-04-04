"""
Plugin manager for EasyMacro.

Handles plugin discovery, loading, and lifecycle management.
"""

import importlib.util
from pathlib import Path
from typing import Type, Optional
from PySide6.QtCore import QObject, Signal

from src.plugins.base import PluginBase, PluginMetadata
from src.core.exceptions import PluginLoadError
from src.core.logger import get_logger


class PluginManager(QObject):
    """
    Manages plugin lifecycle and discovery.
    
    The plugin manager discovers plugins in the plugins directory,
    loads them dynamically, and manages their lifecycle.
    
    Signals:
        plugin_loaded: Emitted when a plugin is loaded (plugin_name)
        plugin_unloaded: Emitted when a plugin is unloaded (plugin_name)
    
    Usage:
        manager = PluginManager(Path("plugins"))
        manager.load_all()
        
        # Later...
        manager.unload("MyPlugin")
    """
    
    # Signals
    plugin_loaded = Signal(str)  # plugin_name
    plugin_unloaded = Signal(str)  # plugin_name
    
    def __init__(self, plugins_dir: Path):
        """Initialize plugin manager.
        
        Args:
            plugins_dir: Directory containing plugin modules.
        
        Raises:
            ValueError: If plugins_dir is None.
        """
        super().__init__()
        
        if plugins_dir is None:
            raise ValueError("Plugins directory cannot be None")
        
        self._plugins_dir = plugins_dir
        self._plugins: dict[str, PluginBase] = {}
        self._logger = get_logger("plugin_manager")
    
    def discover_plugins(self) -> list[Path]:
        """Discover all plugin files in the plugins directory.
        
        Returns:
            List of paths to plugin files.
        """
        if not self._plugins_dir.exists():
            self._logger.warning(f"Plugins directory does not exist: {self._plugins_dir}")
            return []
        
        plugin_files = []
        for file_path in self._plugins_dir.rglob("*.py"):
            # Skip __init__.py and base.py
            if file_path.name in ("__init__.py", "base.py"):
                continue
            plugin_files.append(file_path)
        
        return plugin_files
    
    def load_plugin(self, plugin_path: Path) -> Optional[PluginBase]:
        """Load a plugin from a file path.
        
        Args:
            plugin_path: Path to the plugin file.
        
        Returns:
            Loaded plugin instance, or None if loading failed.
        
        Raises:
            ValueError: If plugin_path is None.
            PluginLoadError: If plugin fails to load.
        """
        if plugin_path is None:
            raise ValueError("Plugin path cannot be None")
        
        if not plugin_path.exists():
            raise PluginLoadError(f"Plugin file does not exist: {plugin_path}")
        
        self._logger.info(f"Loading plugin from {plugin_path}")
        
        try:
            # Load module dynamically
            module_name = plugin_path.stem
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not load module spec from {plugin_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find PluginBase subclass
            plugin_class: Optional[Type[PluginBase]] = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    plugin_class = attr
                    break
            
            if plugin_class is None:
                raise PluginLoadError(
                    f"No PluginBase subclass found in {plugin_path}"
                )
            
            # Instantiate and initialize plugin
            plugin_instance = plugin_class()
            plugin_instance.on_load()
            
            # Store plugin
            self._plugins[plugin_instance.name] = plugin_instance
            self.plugin_loaded.emit(plugin_instance.name)
            
            self._logger.info(f"Successfully loaded plugin: {plugin_instance.name}")
            return plugin_instance
            
        except Exception as e:
            self._logger.error(f"Failed to load plugin from {plugin_path}: {e}")
            raise PluginLoadError(f"Failed to load plugin: {e}") from e
    
    def load_all(self) -> list[PluginBase]:
        """Load all discovered plugins.
        
        Returns:
            List of successfully loaded plugins.
        """
        loaded_plugins = []
        plugin_files = self.discover_plugins()
        
        for plugin_path in plugin_files:
            try:
                plugin = self.load_plugin(plugin_path)
                if plugin is not None:
                    loaded_plugins.append(plugin)
            except PluginLoadError as e:
                self._logger.error(f"Skipping plugin {plugin_path}: {e}")
                continue
        
        return loaded_plugins
    
    def unload(self, plugin_name: str) -> None:
        """Unload a plugin by name.
        
        Args:
            plugin_name: Name of the plugin to unload.
        
        Raises:
            ValueError: If plugin_name is empty.
            PluginLoadError: If plugin is not loaded.
        """
        if not plugin_name:
            raise ValueError("Plugin name cannot be empty")
        
        if plugin_name not in self._plugins:
            raise PluginLoadError(f"Plugin not loaded: {plugin_name}")
        
        plugin = self._plugins[plugin_name]
        plugin.on_unload()
        
        del self._plugins[plugin_name]
        self.plugin_unloaded.emit(plugin_name)
        
        self._logger.info(f"Unloaded plugin: {plugin_name}")
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """Get a loaded plugin by name.
        
        Args:
            plugin_name: Name of the plugin.
        
        Returns:
            Plugin instance, or None if not found.
        """
        return self._plugins.get(plugin_name)
    
    def get_all_plugins(self) -> list[PluginBase]:
        """Get all loaded plugins.
        
        Returns:
            List of all loaded plugins.
        """
        return list(self._plugins.values())
    
    def get_plugin_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """Get metadata for a loaded plugin.
        
        Args:
            plugin_name: Name of the plugin.
        
        Returns:
            Plugin metadata, or None if not found.
        """
        plugin = self.get_plugin(plugin_name)
        if plugin is None:
            return None
        return plugin.metadata
    
    def is_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded.
        
        Args:
            plugin_name: Name of the plugin.
        
        Returns:
            True if loaded, False otherwise.
        """
        return plugin_name in self._plugins


# Global singleton instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance.
    
    Raises:
        RuntimeError: If plugin manager not initialized.
    
    Returns:
        PluginManager: The global plugin manager instance.
    """
    if _plugin_manager is None:
        raise RuntimeError("Plugin manager not initialized. Call init_plugin_manager() first.")
    return _plugin_manager


def init_plugin_manager(plugins_dir: Path) -> PluginManager:
    """Initialize the global plugin manager.
    
    Args:
        plugins_dir: Directory containing plugin modules.
    
    Returns:
        PluginManager: The newly created plugin manager instance.
    
    Raises:
        RuntimeError: If plugin manager already initialized.
    """
    global _plugin_manager
    if _plugin_manager is not None:
        raise RuntimeError("Plugin manager already initialized.")
    _plugin_manager = PluginManager(plugins_dir)
    return _plugin_manager
