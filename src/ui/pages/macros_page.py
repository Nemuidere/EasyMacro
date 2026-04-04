"""
Macros page for EasyMacro.

Shows macro list and allows editing.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
)
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.services.macro_service import get_macro_service
from src.models.macro import Macro
from src.models.action import ClickAction, DelayAction


class MacrosPage(QWidget):
    """
    Macros page for managing macros.
    
    Displays:
    - List of macros
    - Add/Edit/Delete buttons
    - Macro details
    """
    
    # Signals
    create_macro_requested = Signal()
    edit_macro_requested = Signal(str)  # macro_id
    delete_macro_requested = Signal(str)  # macro_id
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize macros page.
        
        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("macrosPage")
        
        self._setup_ui()
        self._connect_signals()
        self._load_macros()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Page title
        title = QLabel("Macros")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        layout.addWidget(title)
        
        subtitle = QLabel("Create and manage your macros")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(15)
        
        self._add_button = QPushButton("Add Macro")
        self._add_button.setObjectName("primaryButton")
        toolbar.addWidget(self._add_button)
        
        self._edit_button = QPushButton("Edit")
        self._edit_button.setEnabled(False)
        toolbar.addWidget(self._edit_button)
        
        self._delete_button = QPushButton("Delete")
        self._delete_button.setObjectName("dangerButton")
        self._delete_button.setEnabled(False)
        toolbar.addWidget(self._delete_button)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Macro list
        self._macro_list = QListWidget()
        self._macro_list.setObjectName("macroList")
        layout.addWidget(self._macro_list, 1)
    
    def _connect_signals(self) -> None:
        """Connect button signals."""
        self._add_button.clicked.connect(self._on_add_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._macro_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._macro_list.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def _load_macros(self) -> None:
        """Load macros from service."""
        self._macro_list.clear()
        
        try:
            service = get_macro_service()
            macros = service.get_all()
            
            for macro in macros:
                item = QListWidgetItem(macro.name)
                item.setData(Qt.UserRole, macro.id)
                
                # Add status indicator
                if macro.enabled:
                    item.setToolTip(f"{macro.name} (Enabled)")
                else:
                    item.setToolTip(f"{macro.name} (Disabled)")
                
                self._macro_list.addItem(item)
                
        except Exception as e:
            # Show error in UI
            pass
    
    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        # Create a simple macro for now
        # TODO: Show macro editor dialog
        try:
            service = get_macro_service()
            macro = Macro(
                name="New Macro",
                description="Click to edit",
                actions=[
                    ClickAction(x=100, y=100),
                    DelayAction(duration_ms=500),
                ]
            )
            service.save(macro)
            self._load_macros()
        except RuntimeError:
            pass  # Service not initialized
    
    def _on_edit_clicked(self) -> None:
        """Handle edit button click."""
        current_item = self._macro_list.currentItem()
        if current_item:
            macro_id = current_item.data(Qt.UserRole)
            self.edit_macro_requested.emit(macro_id)
    
    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return

        macro_id = current_item.data(Qt.UserRole)

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Macro",
            "Are you sure you want to delete this macro?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                service = get_macro_service()
                service.delete(macro_id)
                self._load_macros()
            except RuntimeError:
                pass  # Service not initialized
    
    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        has_selection = self._macro_list.currentItem() is not None
        self._edit_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle item double click.
        
        Args:
            item: Clicked item.
        """
        macro_id = item.data(Qt.UserRole)
        self.edit_macro_requested.emit(macro_id)
    
    def refresh(self) -> None:
        """Refresh the macro list."""
        self._load_macros()
