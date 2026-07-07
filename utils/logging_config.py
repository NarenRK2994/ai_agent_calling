"""Logging utilities for the ERP AI Agent."""

from __future__ import annotations

import logging
from pathlib import Path

from config import LoggingConfig


def configure_logging(config: LoggingConfig) -> None:
    """Configure root logging handlers."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if config.log_file:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(Path(config.log_file), encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, config.level.upper(), logging.INFO),
        format=config.format,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""
    return logging.getLogger(name)
