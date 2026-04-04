"""
Main window for EasyMacro.

Contains the sidebar navigation and page container.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.macros_page import MacrosPage
from src.ui.pages.settings_page import SettingsPage


class NavButton(QPushButton):
    """Navigation button for the sidebar.
    
    A styled button that can be checked to indicate the active page.
    """
    
    def __init__(self, text: str, parent: Optional[QWidget] = None):
        """Initialize navigation button.
        
        Args:
            text: Button text.
            parent: Optional parent widget.
        """
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)


class MainWindow(QMainWindow):
    """
    Main application window.
    
    Contains a sidebar for navigation and a stacked widget for pages.
    
    Signals:
        close_event: Emitted when the window is about to close.
    
    Usage:
        window = MainWindow()
        window.show()
    """
    
    # Signals
    close_event = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize main window.
        
        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        
        self._pages: dict[str, QWidget] = {}
        self._current_page: Optional[str] = None
        
        self._setup_ui()
        self._create_pages()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Central widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Page container
        self._page_container = QStackedWidget()
        main_layout.addWidget(self._page_container, 1)
    
    def _create_sidebar(self) -> QWidget:
        """Create the sidebar widget.
        
        Returns:
            Sidebar widget.
        """
        sidebar = QWidget()
        sidebar.setObjectName("sidebarWidget")
        sidebar.setFixedWidth(200)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo/Title
        title_label = QLabel("EasyMacro")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        layout.addWidget(title_label)
        
        # Spacer
        layout.addSpacing(30)
        
        # Navigation buttons
        self._nav_buttons: dict[str, NavButton] = {}
        
        nav_items = [
            ("dashboard", "Dashboard"),
            ("macros", "Macros"),
            ("settings", "Settings"),
        ]
        
        for page_id, page_name in nav_items:
            button = NavButton(page_name)
            button.setObjectName(f"nav_{page_id}")
            button.clicked.connect(lambda checked, pid=page_id: self._navigate_to(pid))
            layout.addWidget(button)
            self._nav_buttons[page_id] = button
        
        # Spacer
        layout.addStretch()
        
        # Version label
        version_label = QLabel("v0.1.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setObjectName("versionLabel")
        layout.addWidget(version_label)
        
        return sidebar
    
    def _create_pages(self) -> None:
        """Create and add pages to the container."""
        # Dashboard page
        dashboard = DashboardPage()
        self._add_page("dashboard", dashboard)
        
        # Macros page
        macros = MacrosPage()
        self._add_page("macros", macros)
        
        # Settings page
        settings = SettingsPage()
        self._add_page("settings", settings)
        
        # Navigate to dashboard by default
        self._navigate_to("dashboard")
    
    def _add_page(self, page_id: str, page: QWidget) -> None:
        """Add a page to the container.
        
        Args:
            page_id: Unique page identifier.
            page: Page widget.
        """
        self._pages[page_id] = page
        self._page_container.addWidget(page)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        pass
    
    def _navigate_to(self, page_id: str) -> None:
        """Navigate to a page.
        
        Args:
            page_id: Page identifier.
        
        Raises:
            ValueError: If page_id is not found.
        """
        if page_id not in self._pages:
            raise ValueError(f"Page not found: {page_id}")
        
        # Update button states
        for pid, button in self._nav_buttons.items():
            button.setChecked(pid == page_id)
        
        # Switch page
        page = self._pages[page_id]
        self._page_container.setCurrentWidget(page)
        self._current_page = page_id
    
    def closeEvent(self, event) -> None:
        """Handle window close event.
        
        Args:
            event: Close event.
        """
        self.close_event.emit()
        event.ignore()  # We'll handle closing ourselves
    
    def get_current_page(self) -> Optional[str]:
        """Get the current page identifier.
        
        Returns:
            Current page ID or None.
        """
        return self._current_page
