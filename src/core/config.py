"""
Configuration management for EasyMacro.

Handles application settings with JSON persistence and type-safe access.
"""

import json
from pathlib import Path
from typing import Any, TypeVar, Type
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class ConfigManager:
    """
    Manages application configuration with JSON persistence.
    
    Configuration is stored in a JSON file and loaded on demand.
    Changes are automatically persisted to disk.
    
    Usage:
        config = ConfigManager(Path("data/config.json"))
        settings = config.get_settings(AppSettings)
        settings.theme = "dark"
        config.save(settings)
    """
    
    def __init__(self, config_path: Path):
        """Initialize config manager.
        
        Args:
            config_path: Path to the JSON config file.
        
        Raises:
            ValueError: If config_path is None.
        """
        if config_path is None:
            raise ValueError("Config path cannot be None")
        
        self._config_path = config_path
        self._ensure_config_exists()
    
    def _ensure_config_exists(self) -> None:
        """Ensure config file exists, create if missing."""
        if self._config_path.exists():
            return
        
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text("{}")
    
    def load(self, model_class: Type[T]) -> T:
        """Load configuration into a Pydantic model.
        
        Args:
            model_class: Pydantic model class to load into.
        
        Returns:
            Instance of model_class with loaded data.
        
        Raises:
            ValueError: If model_class is None.
            json.JSONDecodeError: If config file is invalid JSON.
        """
        if model_class is None:
            raise ValueError("Model class cannot be None")
        
        try:
            data = json.loads(self._config_path.read_text())
            return model_class.model_validate(data)
        except json.JSONDecodeError:
            return model_class()
    
    def save(self, model: BaseModel) -> None:
        """Save configuration from a Pydantic model.
        
        Args:
            model: Pydantic model to save.
        
        Raises:
            ValueError: If model is None.
        """
        if model is None:
            raise ValueError("Model cannot be None")
        
        self._config_path.write_text(
            json.dumps(model.model_dump(), indent=2, default=str)
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.
        
        Args:
            key: Configuration key.
            default: Default value if key not found.
        
        Returns:
            Configuration value or default.
        
        Raises:
            ValueError: If key is empty.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        
        data = json.loads(self._config_path.read_text())
        return data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key.
        
        Args:
            key: Configuration key.
            value: Value to set.
        
        Raises:
            ValueError: If key is empty.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        
        data = json.loads(self._config_path.read_text())
        data[key] = value
        self._config_path.write_text(json.dumps(data, indent=2, default=str))
