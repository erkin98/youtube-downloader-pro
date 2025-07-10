"""
Logging configuration for the application
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Setup application logging"""

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if settings.DEBUG:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        console_formatter = JSONFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler for application logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # Access log handler (for uvicorn)
    access_handler = logging.handlers.RotatingFileHandler(
        log_dir / "access.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    access_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    access_handler.setFormatter(access_formatter)

    # Configure specific loggers
    loggers = {
        "uvicorn.access": {
            "level": logging.INFO,
            "handlers": [access_handler],
            "propagate": False,
        },
        "uvicorn.error": {
            "level": logging.INFO,
            "propagate": True,
        },
        "sqlalchemy.engine": {
            "level": logging.WARNING,
            "propagate": True,
        },
        "aioredis": {
            "level": logging.WARNING,
            "propagate": True,
        },
    }

    for logger_name, config in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(config["level"])
        logger.propagate = config.get("propagate", True)

        if "handlers" in config:
            for handler in config["handlers"]:
                logger.addHandler(handler)


class LoggerMixin:
    """Mixin to add logging capabilities to classes"""

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__name__)

    def log_info(self, message: str, **kwargs):
        """Log info message with extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)

    def log_error(self, message: str, **kwargs):
        """Log error message with extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.error(message, extra=extra)

    def log_warning(self, message: str, **kwargs):
        """Log warning message with extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)

    def log_debug(self, message: str, **kwargs):
        """Log debug message with extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.debug(message, extra=extra)
