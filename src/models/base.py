"""
Base models for EasyMacro.

Provides Pydantic base classes for data validation at boundaries.
"""

from typing import Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
import uuid


def generate_id() -> str:
    """Generate a unique identifier.
    
    Returns:
        A UUID string.
    """
    return str(uuid.uuid4())


class EasyMacroBaseModel(BaseModel):
    """
    Base model for all EasyMacro data models.
    
    Provides common configuration and methods for all models:
    - UUID generation
    - Timestamp tracking
    - JSON serialization
    
    All models should inherit from this class to ensure
    consistent behavior across the application.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        extra="forbid",
        str_strip_whitespace=True,
    )
    
    id: str = Field(default_factory=generate_id)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary.
        
        Returns:
            Dictionary representation of the model.
        """
        return self.model_dump()
    
    def to_json(self) -> str:
        """Convert model to JSON string.
        
        Returns:
            JSON string representation of the model.
        """
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EasyMacroBaseModel":
        """Create model from dictionary.
        
        Args:
            data: Dictionary to create model from.
        
        Returns:
            Model instance.
        """
        return cls.model_validate(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "EasyMacroBaseModel":
        """Create model from JSON string.
        
        Args:
            json_str: JSON string to create model from.
        
        Returns:
            Model instance.
        """
        return cls.model_validate_json(json_str)
