"""
Dashboard page for EasyMacro.

Shows macro status, quick actions, and recent activity.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.core.state import get_state_manager, AppState
from src.core.macro_engine import get_macro_engine
from src.services.macro_service import get_macro_service


class StatusCard(QFrame):
    """A card widget displaying status information.
    
    Shows a title, value, and optional subtitle.
    """
    
    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        parent: Optional[QWidget] = None
    ):
        """Initialize status card.
        
        Args:
            title: Card title.
            value: Main value to display.
            subtitle: Optional subtitle.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("statusCard")
        
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
    
    def set_value(self, value: str) -> None:
        """Set the card value.
        
        Args:
            value: New value.
        """
        self._value_label.setText(value)


class DashboardPage(QWidget):
    """
    Dashboard page showing macro status and quick actions.
    
    Displays:
    - Current macro status
    - Active macro progress
    - Quick action buttons
    - Recent execution log
    """
    
    # Signals
    start_macro_requested = Signal(str)  # macro_id
    stop_macro_requested = Signal()
    pause_macro_requested = Signal()
    resume_macro_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize dashboard page.
        
        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("dashboardPage")
        
        self._setup_ui()
        self._connect_signals()
        self._update_status()
    
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
        
        subtitle = QLabel("Monitor and control your macros")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        
        # Status cards
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)
        
        self._status_card = StatusCard("Status", "Idle", "No macro running")
        cards_layout.addWidget(self._status_card, 0, 0)
        
        self._active_macro_card = StatusCard("Active Macro", "None", "Select a macro to run")
        cards_layout.addWidget(self._active_macro_card, 0, 1)
        
        self._total_macros_card = StatusCard("Total Macros", "0", "Configured macros")
        cards_layout.addWidget(self._total_macros_card, 0, 2)
        
        layout.addLayout(cards_layout)
        
        # Quick actions
        actions_frame = QFrame()
        actions_frame.setObjectName("actionsFrame")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setSpacing(15)
        
        self._start_button = QPushButton("Start")
        self._start_button.setObjectName("primaryButton")
        self._start_button.setEnabled(False)
        actions_layout.addWidget(self._start_button)
        
        self._pause_button = QPushButton("Pause")
        self._pause_button.setEnabled(False)
        actions_layout.addWidget(self._pause_button)
        
        self._stop_button = QPushButton("Stop")
        self._stop_button.setObjectName("dangerButton")
        self._stop_button.setEnabled(False)
        actions_layout.addWidget(self._stop_button)
        
        actions_layout.addStretch()
        
        layout.addWidget(actions_frame)
        
        # Recent activity (placeholder)
        activity_label = QLabel("Recent Activity")
        activity_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(activity_label)
        
        self._activity_placeholder = QLabel("No recent activity")
        self._activity_placeholder.setObjectName("activityPlaceholder")
        layout.addWidget(self._activity_placeholder)
        
        layout.addStretch()
    
    def _connect_signals(self) -> None:
        """Connect button signals."""
        self._start_button.clicked.connect(self._on_start_clicked)
        self._pause_button.clicked.connect(self._on_pause_clicked)
        self._stop_button.clicked.connect(self._on_stop_clicked)

        # Connect to macro engine signals
        try:
            engine = get_macro_engine()
            engine.macro_started.connect(self._on_macro_started)
            engine.macro_completed.connect(self._on_macro_completed)
            engine.macro_error.connect(self._on_macro_error)
        except RuntimeError:
            pass  # Engine not initialized yet
    
    def _update_status(self) -> None:
        """Update status display."""
        state_manager = get_state_manager()
        
        if state_manager.is_idle():
            self._status_card.set_value("Idle")
            self._status_card.setStyleSheet("")
            self._start_button.setEnabled(True)
            self._pause_button.setEnabled(False)
            self._stop_button.setEnabled(False)
        elif state_manager.is_running():
            self._status_card.set_value("Running")
            self._status_card.setStyleSheet("QFrame { border-color: #4CAF50; }")
            self._start_button.setEnabled(False)
            self._pause_button.setEnabled(True)
            self._stop_button.setEnabled(True)
        elif state_manager.is_paused():
            self._status_card.set_value("Paused")
            self._status_card.setStyleSheet("QFrame { border-color: #FFC107; }")
            self._start_button.setEnabled(False)
            self._pause_button.setEnabled(False)
            self._stop_button.setEnabled(True)
        elif state_manager.is_error():
            error = state_manager.get_error() or "Unknown error"
            self._status_card.set_value("Error")
            self._status_card.setStyleSheet("QFrame { border-color: #F44336; }")
            self._start_button.setEnabled(True)
            self._pause_button.setEnabled(False)
            self._stop_button.setEnabled(False)
    
    def _on_macro_started(self, macro_id: str) -> None:
        """Handle macro started event."""
        self._update_status()

    def _on_macro_completed(self, macro_id: str) -> None:
        """Handle macro completed event."""
        self._update_status()

    def _on_macro_error(self, macro_id: str, error: str) -> None:
        """Handle macro error event."""
        self._update_status()
        # Show error in UI
        self._activity_placeholder.setText(f"Error: {error}")

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        # Get first enabled macro
        try:
            service = get_macro_service()
            macros = service.get_enabled()

            if not macros:
                self._activity_placeholder.setText("No macros available")
                return

            # Start first macro
            engine = get_macro_engine()
            engine.run_macro(macros[0])

        except RuntimeError:
            pass  # Services not initialized
        except Exception as e:
            self._activity_placeholder.setText(f"Error: {e}")
    
    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        self.pause_macro_requested.emit()
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.stop_macro_requested.emit()
    
    def refresh(self) -> None:
        """Refresh the dashboard."""
        self._update_status()
