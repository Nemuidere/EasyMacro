"""
Main application controller for EasyMacro.

Handles application initialization, system tray, and global state.
"""

import sys
import logging
from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, Signal

from src.ui.main_window import MainWindow
from src.core.config import ConfigManager
from src.core.logger import setup_logger, get_logger
from src.core.event_bus import init_event_bus, get_event_bus
from src.core.state import init_state_manager, get_state_manager
from src.core.randomization import init_randomization_engine
from src.core.hotkey_manager import init_hotkey_manager, get_hotkey_manager
from src.services.macro_service import init_macro_service, get_macro_service
from src.services.ahk_service import init_ahk_service
from src.models.settings import AppSettings, RandomizationSettings


class Application(QObject):
    """
    Main application controller.
    
    Handles initialization, system tray, and coordinates between components.
    
    Usage:
        app = Application(sys.argv)
        app.run()
    """
    
    # Signals
    ready = Signal()
    shutdown_requested = Signal()
    
    def __init__(self, argv: list[str]):
        """Initialize the application.
        
        Args:
            argv: Command line arguments.
        
        Raises:
            ValueError: If argv is None.
        """
        super().__init__()
        
        if argv is None:
            raise ValueError("argv cannot be None")
        
        self._argv = argv
        self._qt_app: Optional[QApplication] = None
        self._main_window: Optional[MainWindow] = None
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._config_manager: Optional[ConfigManager] = None
        self._settings: Optional[AppSettings] = None
        self._logger: Optional[logging.Logger] = None
        
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize all application components."""
        # Initialize Qt application
        self._qt_app = QApplication(self._argv)
        self._qt_app.setApplicationName("EasyMacro")
        self._qt_app.setApplicationVersion("0.1.0")
        self._qt_app.setOrganizationName("EasyMacro")
        
        # Initialize logging
        self._initialize_logging()
        
        # Load settings
        self._initialize_settings()
        
        # Initialize core components
        self._initialize_core()
        
        # Initialize services
        self._initialize_services()
        
        # Create main window
        self._create_main_window()
        
        # Create system tray
        self._create_system_tray()
        
        # Connect signals
        self._connect_signals()
        
        self._logger.info("Application initialized successfully")
    
    def _initialize_logging(self) -> None:
        """Initialize logging system."""
        log_path = Path("data/logs/easymacro.log")
        setup_logger("easymacro", log_path)
        self._logger = get_logger("app")
    
    def _initialize_settings(self) -> None:
        """Initialize settings from config file."""
        config_path = Path("data/config.json")
        self._config_manager = ConfigManager(config_path)
        self._settings = self._config_manager.load(AppSettings)
    
    def _initialize_core(self) -> None:
        """Initialize core components."""
        # Event bus
        init_event_bus()
        
        # State manager
        init_state_manager()
        
        # Randomization engine
        init_randomization_engine(self._settings.randomization)
        
        # Hotkey manager
        init_hotkey_manager()
    
    def _initialize_services(self) -> None:
        """Initialize services."""
        macros_path = Path("data/macros.json")
        init_macro_service(macros_path)

        # Initialize AHK service - fails fast if AHK is not available
        init_ahk_service()
        self._logger.info("AHK service initialized")
    
    def _create_main_window(self) -> None:
        """Create the main window."""
        self._main_window = MainWindow()
        self._main_window.setWindowTitle("EasyMacro")
        self._main_window.setMinimumSize(800, 600)
        
        # Apply stylesheet
        self._apply_theme()
    
    def _create_system_tray(self) -> None:
        """Create the system tray icon."""
        # Create tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)
        
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self._hide_window)
        tray_menu.addAction(hide_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)
        
        # Create tray icon
        self._tray_icon = QSystemTrayIcon()
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.setToolTip("EasyMacro")
        
        # Double-click to show/hide
        self._tray_icon.activated.connect(self._on_tray_activated)
        
        # TODO: Set proper icon
        # self._tray_icon.setIcon(QIcon("resources/icons/tray.png"))
    
    def _apply_theme(self) -> None:
        """Apply the current theme."""
        theme_path = Path("resources/styles/dark_theme.qss")
        if theme_path.exists():
            stylesheet = theme_path.read_text()
            self._qt_app.setStyleSheet(stylesheet)
    
    def _connect_signals(self) -> None:
        """Connect application signals."""
        event_bus = get_event_bus()
        
        event_bus.app_shutdown.connect(self._quit_app)
        
        # Handle window close
        self._main_window.close_event.connect(self._on_window_close)
    
    def _show_window(self) -> None:
        """Show the main window."""
        if self._main_window:
            self._main_window.show()
            self._main_window.activateWindow()
    
    def _hide_window(self) -> None:
        """Hide the main window."""
        if self._main_window:
            self._main_window.hide()
    
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation.
        
        Args:
            reason: Activation reason.
        """
        if reason == QSystemTrayIcon.DoubleClick:
            if self._main_window and self._main_window.isVisible():
                self._hide_window()
            else:
                self._show_window()
    
    def _on_window_close(self) -> None:
        """Handle main window close event."""
        if self._settings and self._settings.close_to_tray:
            self._hide_window()
        else:
            self._quit_app()
    
    def _quit_app(self) -> None:
        """Quit the application."""
        self._logger.info("Shutting down application")
        
        # Stop hotkey manager
        hotkey_manager = get_hotkey_manager()
        hotkey_manager.stop()
        
        # Save settings
        if self._config_manager and self._settings:
            self._config_manager.save(self._settings)
        
        # Quit Qt application
        self._qt_app.quit()
    
    def run(self) -> int:
        """Run the application.
        
        Returns:
            Exit code.
        """
        self._logger.info("Starting application")
        
        # Show tray icon
        if self._tray_icon:
            self._tray_icon.show()
        
        # Show main window (or start minimized)
        if self._settings and not self._settings.start_minimized:
            self._show_window()
        
        # Start hotkey manager
        hotkey_manager = get_hotkey_manager()
        hotkey_manager.start()
        
        # Emit ready signal
        self.ready.emit()
        
        return self._qt_app.exec()


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code.
    """
    app = Application(sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
