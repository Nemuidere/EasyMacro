"""
Stats models for EasyMacro.

Defines statistics tracking models for macro usage analytics.
"""

from datetime import datetime
from typing import Optional
from pydantic import Field

from src.models.base import EasyMacroBaseModel


class MacroStats(EasyMacroBaseModel):
    """Statistics for a single macro.
    
    Tracks usage metrics for individual macros including
    total clicks, execution time, and last usage timestamp.
    
    Attributes:
        macro_id: Reference to the macro being tracked.
        total_clicks: Total number of clicks executed by this macro.
        total_time_seconds: Total execution time in seconds.
        last_used_at: UTC timestamp of last execution, None if never used.
    """
    
    macro_id: str = Field(description="Reference to the macro")
    total_clicks: int = Field(default=0, ge=0, description="Total clicks executed")
    total_time_seconds: float = Field(default=0.0, ge=0.0, description="Total execution time in seconds")
    last_used_at: Optional[datetime] = Field(default=None, description="UTC timestamp of last use")


class GlobalStats(EasyMacroBaseModel):
    """Global statistics across all macros.
    
    Aggregates statistics for the entire application including
    total macros, combined clicks, and time across all executions.
    
    Attributes:
        total_macros: Total number of macros tracked.
        total_clicks: Combined click count across all macros.
        total_time_seconds: Combined execution time across all macros.
        last_used_macro_id: ID of the most recently executed macro.
        macro_stats: Dictionary of per-macro statistics keyed by macro_id.
    """
    
    total_macros: int = Field(default=0, ge=0, description="Total macros tracked")
    total_clicks: int = Field(default=0, ge=0, description="Combined clicks across all macros")
    total_time_seconds: float = Field(default=0.0, ge=0.0, description="Combined execution time in seconds")
    last_used_macro_id: Optional[str] = Field(default=None, description="Most recently used macro ID")
    macro_stats: dict[str, MacroStats] = Field(default_factory=dict, description="Per-macro statistics keyed by macro_id")
