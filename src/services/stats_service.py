"""
Statistics service for EasyMacro.

Provides thread-safe statistics tracking with persistence.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QMutex, QMutexLocker

from src.models.stats import MacroStats, GlobalStats
from src.core.constants import DEFAULT_STATS_PATH
from src.core.event_bus import get_event_bus


class StatsService:
    """
    Thread-safe statistics tracking service.
    
    Tracks macro usage statistics including clicks, execution time,
    and aggregates across all macros. Persists data to JSON file.
    
    Uses QMutex for thread-safe access to shared state.
    On write failure: logs error, continues in-memory, retries next update.
    On read failure: resets to defaults, logs warning.
    
    Usage:
        service = StatsService()
        service.update_clicks("macro_123", 5)
        stats = service.get_global_stats()
    """
    
    def __init__(self, stats_path: Optional[Path] = None):
        """Initialize statistics service.
        
        Args:
            stats_path: Path to stats JSON file. Uses DEFAULT_STATS_PATH if None.
        """
        self._mutex = QMutex()
        self._stats_path = stats_path or DEFAULT_STATS_PATH
        self._logger = logging.getLogger("stats_service")
        self._event_bus = get_event_bus()
        
        self._global_stats: GlobalStats = GlobalStats()
        self._load()
    
    def update_clicks(self, macro_id: str, count: int = 1) -> None:
        """Increment click count for a macro.
        
        Updates both per-macro and global statistics. Emits stats_updated
        signal after updating. Persists to disk.
        
        Args:
            macro_id: ID of the macro being tracked.
            count: Number of clicks to add (default 1).
        
        Raises:
            ValueError: If macro_id is empty or count is negative.
        """
        if not macro_id:
            raise ValueError("Macro ID cannot be empty")
        if count < 0:
            raise ValueError(f"Click count cannot be negative, got {count}")
        if count == 0:
            return
        
        with QMutexLocker(self._mutex):
            self._update_clicks_internal(macro_id, count)
        
        self._save()
        self._emit_stats_updated(macro_id)
    
    def _update_clicks_internal(self, macro_id: str, count: int) -> None:
        """Internal method to update click counts (mutex already held).
        
        Args:
            macro_id: ID of the macro.
            count: Number of clicks to add.
        """
        macro_stats = self._get_or_create_macro_stats(macro_id)
        macro_stats.total_clicks += count
        macro_stats.last_used_at = datetime.now()
        
        self._global_stats.total_clicks += count
        self._global_stats.last_used_macro_id = macro_id
    
    def update_time(self, macro_id: str, seconds: float) -> None:
        """Increment execution time for a macro.
        
        Updates both per-macro and global statistics. Persists to disk.
        
        Args:
            macro_id: ID of the macro being tracked.
            seconds: Execution time in seconds to add.
        
        Raises:
            ValueError: If macro_id is empty or seconds is negative.
        """
        if not macro_id:
            raise ValueError("Macro ID cannot be empty")
        if seconds < 0:
            raise ValueError(f"Time cannot be negative, got {seconds}")
        if seconds == 0:
            return
        
        with QMutexLocker(self._mutex):
            self._update_time_internal(macro_id, seconds)
        
        self._save()
    
    def _update_time_internal(self, macro_id: str, seconds: float) -> None:
        """Internal method to update time (mutex already held).
        
        Args:
            macro_id: ID of the macro.
            seconds: Time in seconds to add.
        """
        macro_stats = self._get_or_create_macro_stats(macro_id)
        macro_stats.total_time_seconds += seconds
        macro_stats.last_used_at = datetime.now()
        
        self._global_stats.total_time_seconds += seconds
        self._global_stats.last_used_macro_id = macro_id
    
    def _get_or_create_macro_stats(self, macro_id: str) -> MacroStats:
        """Get existing macro stats or create new ones.
        
        Args:
            macro_id: ID of the macro.
        
        Returns:
            MacroStats instance for the macro.
        """
        if macro_id not in self._global_stats.macro_stats:
            self._global_stats.macro_stats[macro_id] = MacroStats(macro_id=macro_id)
            self._global_stats.total_macros += 1
        
        return self._global_stats.macro_stats[macro_id]
    
    def get_global_stats(self) -> GlobalStats:
        """Get global statistics across all macros.
        
        Returns:
            Copy of global statistics.
        """
        with QMutexLocker(self._mutex):
            return self._global_stats.model_copy(deep=True)
    
    def get_macro_stats(self, macro_id: str) -> Optional[MacroStats]:
        """Get statistics for a specific macro.
        
        Args:
            macro_id: ID of the macro to look up.
        
        Returns:
            MacroStats if found, None otherwise.
        
        Raises:
            ValueError: If macro_id is empty.
        """
        if not macro_id:
            raise ValueError("Macro ID cannot be empty")
        
        with QMutexLocker(self._mutex):
            stats = self._global_stats.macro_stats.get(macro_id)
            return stats.model_copy(deep=True) if stats else None
    
    def save(self) -> None:
        """Persist statistics to file.
        
        Thread-safe. On failure, logs error and continues with in-memory state.
        The next update will trigger another save attempt.
        """
        self._save()
        self._event_bus.stats_saved.emit()
    
    def _save(self) -> None:
        """Internal save method with error handling."""
        try:
            with QMutexLocker(self._mutex):
                data = self._global_stats.model_dump()
            
            self._stats_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._stats_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            self._logger.debug(f"Stats saved to {self._stats_path}")
            
        except (OSError, IOError, TypeError) as e:
            self._logger.error(f"Failed to save stats: {e}")
    
    def load(self) -> None:
        """Load statistics from file.
        
        Thread-safe. On corruption or read failure, resets to defaults
        and logs a warning.
        """
        self._load()
    
    def _load(self) -> None:
        """Internal load method with error handling."""
        if not self._stats_path.exists():
            self._logger.debug("No stats file found, using defaults")
            return
        
        try:
            with open(self._stats_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with QMutexLocker(self._mutex):
                self._global_stats = GlobalStats.model_validate(data)
            
            self._logger.info(f"Stats loaded from {self._stats_path}")
            
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            self._logger.warning(f"Stats file corrupted, resetting to defaults: {e}")
            with QMutexLocker(self._mutex):
                self._global_stats = GlobalStats()
                
        except (OSError, IOError) as e:
            self._logger.warning(f"Failed to read stats file, using defaults: {e}")
            with QMutexLocker(self._mutex):
                self._global_stats = GlobalStats()
    
    def _emit_stats_updated(self, macro_id: str) -> None:
        """Emit stats_updated signal with current values.
        
        Args:
            macro_id: ID of the macro that was updated.
        """
        macro_stats = self.get_macro_stats(macro_id)
        if macro_stats is None:
            return
        
        self._event_bus.stats_updated.emit(
            macro_id,
            macro_stats.total_clicks,
            macro_stats.total_time_seconds
        )
    
    def reset_all_stats(self) -> None:
        """Reset all statistics to defaults.
        
        Clears all tracked data and persists empty state.
        """
        with QMutexLocker(self._mutex):
            self._global_stats = GlobalStats()
        
        self._save()
        self._logger.info("All statistics reset")
    
    def reset_macro_stats(self, macro_id: str) -> None:
        """Reset statistics for a specific macro.
        
        Args:
            macro_id: ID of the macro to reset.
        
        Raises:
            ValueError: If macro_id is empty.
        """
        if not macro_id:
            raise ValueError("Macro ID cannot be empty")
        
        with QMutexLocker(self._mutex):
            if macro_id in self._global_stats.macro_stats:
                old_stats = self._global_stats.macro_stats.pop(macro_id)
                self._global_stats.total_macros -= 1
                self._global_stats.total_clicks -= old_stats.total_clicks
                self._global_stats.total_time_seconds -= old_stats.total_time_seconds
                
                if self._global_stats.last_used_macro_id == macro_id:
                    self._global_stats.last_used_macro_id = None
        
        self._save()
        self._logger.info(f"Stats reset for macro {macro_id}")


# Global singleton instance
_stats_service: Optional[StatsService] = None


def get_stats_service() -> StatsService:
    """Get the global stats service instance.
    
    Raises:
        RuntimeError: If stats service not initialized.
    
    Returns:
        StatsService: The global stats service instance.
    """
    if _stats_service is None:
        raise RuntimeError("Stats service not initialized. Call init_stats_service() first.")
    
    return _stats_service


def init_stats_service(stats_path: Optional[Path] = None) -> StatsService:
    """Initialize the global stats service.
    
    Args:
        stats_path: Optional path to stats file.
    
    Returns:
        StatsService: The newly created stats service instance.
    
    Raises:
        RuntimeError: If stats service already initialized.
    """
    global _stats_service
    
    if _stats_service is not None:
        raise RuntimeError("Stats service already initialized.")
    
    _stats_service = StatsService(stats_path)
    return _stats_service
