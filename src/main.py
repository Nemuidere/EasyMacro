"""
EasyMacro Entry Point

This is the main entry point for the EasyMacro application.
"""

import sys
from PySide6.QtWidgets import QApplication


def main():
    """Main entry point for EasyMacro."""
    app = QApplication(sys.argv)
    # TODO: Initialize application
    app.setApplicationName("EasyMacro")
    app.setApplicationVersion("0.1.0")
    
    # TODO: Create main window
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
