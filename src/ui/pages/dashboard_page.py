"""
Dashboard page for EasyMacro.

Shows macro statistics, status bar, and hotkey configuration overview.
"""

from typing import Optional
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGridLayout,
    QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.core.state import get_state_manager
from src.core.event_bus import get_event_bus
from src.core.config import ConfigManager
from src.core.constants import DEFAULT_CONFIG_PATH
from src.core.logger import get_logger
from src.services.macro_service import get_macro_service
from src.services.stats_service import get_stats_service
from src.models.settings import AppSettings


class StatsCard(QFrame):
    """A card widget displaying a single statistic.
    
    Shows a title, value, and optional subtitle.
    """
    
    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        parent: Optional[QWidget] = None
    ):
        """Initialize stats card.
        
        Args:
            title: Card title.
            value: Main value to display.
            subtitle: Optional subtitle.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("statsCard")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        
        # Value
        value_label = QLabel(value)
        value_label.setObjectName("cardValue")
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        layout.addWidget(value_label)
        
        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("cardSubtitle")
            layout.addWidget(subtitle_label)
        
        self._value_label = value_label
        self._subtitle_label: Optional[QLabel] = None
        if subtitle:
            self._subtitle_label = subtitle_label
    
    def set_value(self, value: str) -> None:
        """Set the card value.
        
        Args:
            value: New value.
        """
        self._value_label.setText(value)
    
    def set_subtitle(self, subtitle: str) -> None:
        """Set the card subtitle.
        
        Args:
            subtitle: New subtitle.
        """
        if self._subtitle_label:
            self._subtitle_label.setText(subtitle)


class HotkeyRow(QFrame):
    """A row displaying a hotkey assignment."""
    
    def __init__(
        self,
        name: str,
        hotkey: str,
        parent: Optional[QWidget] = None
    ):
        """Initialize hotkey row.
        
        Args:
            name: Name of the action/macro.
            hotkey: The hotkey combination.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("hotkeyRow")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(15)
        
        # Name
        name_label = QLabel(name)
        name_label.setObjectName("hotkeyName")
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        # Hotkey
        hotkey_label = QLabel(hotkey)
        hotkey_label.setObjectName("hotkeyBinding")
        layout.addWidget(hotkey_label)


class DashboardPage(QWidget):
    """
    Dashboard page showing macro statistics and configuration overview.
    
    Displays:
    - Status bar (running macro indicator)
    - Statistics cards (Total Macros, Clicks, Time, Last Used)
    - Configured hotkeys display
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize dashboard page.
        
        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("dashboardPage")
        
        self._logger = get_logger("dashboard_page")
        self._config_manager: Optional[ConfigManager] = None
        
        self._setup_ui()
        self._connect_signals()
        self._refresh_stats()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        layout.addWidget(title)
        
        subtitle = QLabel("Monitor your macro usage and statistics")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        
        # Status bar (Task 2.1)
        self._status_bar = QFrame()
        self._status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(15, 10, 15, 10)
        
        self._status_label = QLabel("No macro running")
        self._status_label.setObjectName("statusLabel")
        status_layout.addWidget(self._status_label)
        
        status_layout.addStretch()
        layout.addWidget(self._status_bar)
        
        # Statistics cards (Task 2.3)
        stats_label = QLabel("Statistics")
        stats_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        stats_label.setObjectName("sectionTitle")
        layout.addWidget(stats_label)
        
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)
        
        self._total_macros_card = StatsCard(
            "Total Macros",
            "0",
            "Configured macros"
        )
        cards_layout.addWidget(self._total_macros_card, 0, 0)
        
        self._total_clicks_card = StatsCard(
            "Total Clicks",
            "0",
            "All time clicks"
        )
        cards_layout.addWidget(self._total_clicks_card, 0, 1)
        
        self._total_time_card = StatsCard(
            "Total Time",
            "00:00:00",
            "Time spent running"
        )
        cards_layout.addWidget(self._total_time_card, 0, 2)
        
        self._last_used_card = StatsCard(
            "Last Used",
            "Never",
            "No recent activity"
        )
        cards_layout.addWidget(self._last_used_card, 0, 3)
        
        layout.addLayout(cards_layout)
        
        # Hotkeys section (Task 2.4)
        hotkeys_label = QLabel("Configured Hotkeys")
        hotkeys_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        hotkeys_label.setObjectName("sectionTitle")
        layout.addWidget(hotkeys_label)
        
        # Hotkeys container
        hotkeys_frame = QFrame()
        hotkeys_frame.setObjectName("hotkeysFrame")
        self._hotkeys_layout = QVBoxLayout(hotkeys_frame)
        self._hotkeys_layout.setContentsMargins(15, 15, 15, 15)
        self._hotkeys_layout.setSpacing(5)
        self._hotkeys_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Scroll area for hotkeys
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(hotkeys_frame)
        scroll.setMaximumHeight(200)
        scroll.setObjectName("hotkeysScrollArea")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        layout.addWidget(scroll)
        
        layout.addStretch()
    
    def _connect_signals(self) -> None:
        """Connect to EventBus signals."""
        try:
            event_bus = get_event_bus()
            event_bus.stats_updated.connect(self._on_stats_updated)
            event_bus.macro_started.connect(self._on_macro_started)
            event_bus.macro_stopped.connect(self._on_macro_stopped)
        except RuntimeError:
            self._logger.warning("Event bus not initialized yet")
    
    def _on_stats_updated(
        self,
        macro_id: str,
        clicks: int,
        time_seconds: float
    ) -> None:
        """Handle stats updated signal.
        
        Args:
            macro_id: ID of the macro that was updated.
            clicks: Total clicks for the macro.
            time_seconds: Total time for the macro.
        """
        self._refresh_stats()
    
    def _on_macro_started(self, macro_id: str) -> None:
        """Handle macro started event.
        
        Args:
            macro_id: ID of the started macro.
        """
        self._update_running_status()
    
    def _on_macro_stopped(self, macro_id: str) -> None:
        """Handle macro stopped event.
        
        Args:
            macro_id: ID of the stopped macro.
        """
        self._update_running_status()
    
    def _update_running_status(self) -> None:
        """Update the status bar based on running macro state."""
        try:
            state_manager = get_state_manager()
            macro_id = state_manager.get_current_macro()
            
            if not macro_id:
                self._status_label.setText("No macro running")
                self._status_label.setProperty("class", "")
                return
            
            macro_service = get_macro_service()
            macro = macro_service.get_by_id(macro_id)
            
            if not macro:
                self._logger.warning(f"Macro with ID '{macro_id}' not found")
                self._status_label.setText("No macro running")
                self._status_label.setProperty("class", "")
                return
            
            self._status_label.setText(f"Running: {macro.name}")
            self._status_label.setProperty("class", "running-macro-text")
                
        except RuntimeError:
            self._logger.warning("State manager or macro service not initialized")
            self._status_label.setText("No macro running")
    
    def _refresh_stats(self) -> None:
        """Refresh all statistics displays."""
        self._update_macro_count()
        self._update_global_stats()
        self._update_running_status()
        self._refresh_hotkeys()
    
    def _update_macro_count(self) -> None:
        """Update the total macros count from MacroService."""
        try:
            macro_service = get_macro_service()
            count = macro_service.count()
            self._total_macros_card.set_value(str(count))
        except RuntimeError:
            self._total_macros_card.set_value("0")
    
    def _update_global_stats(self) -> None:
        """Update statistics from StatsService."""
        try:
            stats_service = get_stats_service()
            global_stats = stats_service.get_global_stats()
            
            # Update clicks
            self._total_clicks_card.set_value(str(global_stats.total_clicks))
            
            # Update time
            formatted_time = self._format_time(global_stats.total_time_seconds)
            self._total_time_card.set_value(formatted_time)
            
            # Update last used
            if global_stats.last_used_macro_id:
                last_macro_stats = stats_service.get_macro_stats(
                    global_stats.last_used_macro_id
                )
                if last_macro_stats and last_macro_stats.last_used_at:
                    time_str = last_macro_stats.last_used_at.strftime("%Y-%m-%d %H:%M")
                    self._last_used_card.set_value(global_stats.last_used_macro_id)
                    self._last_used_card.set_subtitle(f"Last used: {time_str}")
                else:
                    self._last_used_card.set_value(global_stats.last_used_macro_id)
                    self._last_used_card.set_subtitle("Recently used")
            else:
                self._last_used_card.set_value("Never")
                self._last_used_card.set_subtitle("No recent activity")
                
        except RuntimeError:
            # Stats service not initialized
            self._total_clicks_card.set_value("0")
            self._total_time_card.set_value("00:00:00")
            self._last_used_card.set_value("Never")
            self._last_used_card.set_subtitle("No recent activity")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS.
        
        Args:
            seconds: Time in seconds.
        
        Returns:
            Formatted time string (HH:MM:SS).
        """
        if seconds < 0:
            return "00:00:00"
        
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _refresh_hotkeys(self) -> None:
        """Refresh the hotkeys display section."""
        # Clear existing rows
        while self._hotkeys_layout.count() > 0:
            item = self._hotkeys_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add global hotkeys from AppSettings
        try:
            if self._config_manager is None:
                self._config_manager = ConfigManager(DEFAULT_CONFIG_PATH)
            settings = self._config_manager.load(AppSettings)
            
            # Global hotkeys header
            global_header = QLabel("Global Hotkeys")
            global_header.setObjectName("hotkeySectionHeader")
            global_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self._hotkeys_layout.addWidget(global_header)
            
            # Global hotkeys
            self._hotkeys_layout.addWidget(
                HotkeyRow("Pause All", settings.hotkeys.pause_all)
            )
            self._hotkeys_layout.addWidget(
                HotkeyRow("Resume All", settings.hotkeys.resume_all)
            )
            self._hotkeys_layout.addWidget(
                HotkeyRow("Stop All", settings.hotkeys.stop_all)
            )
            
        except Exception as e:
            self._logger.warning(f"Failed to load settings: {e}")
        
        # Add macro hotkeys
        try:
            macro_service = get_macro_service()
            macros = macro_service.get_all()
            macros_with_hotkeys = [m for m in macros if m.hotkey]
            
            if macros_with_hotkeys:
                # Macro hotkeys header
                macro_header = QLabel("Macro Hotkeys")
                macro_header.setObjectName("hotkeySectionHeader")
                macro_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self._hotkeys_layout.addWidget(macro_header)
                
                # Add each macro with hotkey
                for macro in macros_with_hotkeys:
                    self._hotkeys_layout.addWidget(
                        HotkeyRow(macro.name, macro.hotkey or "")
                    )
            
            # Show placeholder if no hotkeys configured
            if self._hotkeys_layout.count() == 0:
                placeholder = QLabel("No hotkeys configured")
                placeholder.setObjectName("hotkeysPlaceholder")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._hotkeys_layout.addWidget(placeholder)
                
        except RuntimeError:
            # Macro service not initialized
            if self._hotkeys_layout.count() == 0:
                placeholder = QLabel("No hotkeys configured")
                placeholder.setObjectName("hotkeysPlaceholder")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._hotkeys_layout.addWidget(placeholder)
    
    def refresh(self) -> None:
        """Refresh the dashboard."""
        self._refresh_stats()
    
    def showEvent(self, event) -> None:
        """Handle page show event.
        
        Args:
            event: The show event.
        """
        super().showEvent(event)
        self._refresh_stats()
