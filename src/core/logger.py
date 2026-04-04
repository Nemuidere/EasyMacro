"""
Logging infrastructure for EasyMacro.

Provides structured logging with file and console handlers.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "easymacro",
    log_file: Optional[Path] = None,
    level: int = logging.INFO
) -> logging.Logger:
    """Set up a logger with file and console handlers.
    
    Args:
        name: Logger name.
        log_file: Optional path to log file.
        level: Logging level.
    
    Returns:
        Configured logger instance.
    
    Raises:
        ValueError: If name is empty.
    """
    if not name:
        raise ValueError("Logger name cannot be empty")
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    logger.handlers.clear()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    if log_file is None:
        return logger
    
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "easymacro") -> logging.Logger:
    """Get an existing logger or create a default one.
    
    Args:
        name: Logger name.
    
    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
