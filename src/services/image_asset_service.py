"""
Reference-image asset storage for EasyMacro.

Screen-condition blocks (if/while/wait) reference a screenshot the user
captured in the builder. The PNG files live under ``data/assets/`` and the
models persist only the filename (see ``ImageCondition.image_file``).

Lifecycle: files are write-once and never deleted by the app. Duplicated
steps/macros safely share the same filename precisely because nothing removes
assets; recapturing a condition simply writes a new file and orphans the old
one. Orphaned PNGs are tiny and harmless — a future maintenance sweep can use
``src.models.action.collect_image_files`` to find what's still referenced.
"""

import uuid
from pathlib import Path

from PySide6.QtGui import QPixmap

from src.core.constants import get_assets_dir


def asset_path(filename: str) -> Path:
    """Absolute path of a reference-image asset.

    Args:
        filename: The bare filename stored on an ImageCondition.

    Returns:
        Absolute path under the assets dir.
    """
    return get_assets_dir() / filename


def save_reference_pixmap(pixmap: QPixmap) -> str:
    """Save a captured screenshot as a new reference-image asset.

    Args:
        pixmap: The captured region screenshot.

    Returns:
        The generated filename (store this on the ImageCondition).

    Raises:
        ValueError: If the pixmap is empty or saving fails.
    """
    if pixmap is None or pixmap.isNull():
        raise ValueError("Cannot save an empty screenshot")

    assets_dir = get_assets_dir()
    assets_dir.mkdir(parents=True, exist_ok=True)

    filename = f"ref_{uuid.uuid4().hex[:12]}.png"
    path = assets_dir / filename
    if not pixmap.save(str(path), "PNG"):
        raise ValueError(f"Failed to save reference image to {path}")
    return filename
