"""
Logging Configuration Module
Provides structured logging with JSON and text formatters
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context"""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add app context
        log_record["app_name"] = settings.APP_NAME
        log_record["app_version"] = settings.APP_VERSION
        log_record["environment"] = settings.APP_ENV


class ColoredFormatter(logging.Formatter):
    """Colored text formatter for console output"""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors"""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for next use
        record.levelname = levelname

        return formatted


def setup_logging() -> None:
    """
    Configure application logging with both JSON and text formatters
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console Handler (colored text for development, JSON for production)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)

    if settings.LOG_FORMAT == "json" or settings.is_production:
        # JSON format
        json_formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s"
        )
        console_handler.setFormatter(json_formatter)
    else:
        # Colored text format for development
        text_format = (
            "%(asctime)s | %(levelname)-8s | %(name)-20s | "
            "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        colored_formatter = ColoredFormatter(text_format, datefmt="%Y-%m-%d %H:%M:%S")
        console_handler.setFormatter(colored_formatter)

    root_logger.addHandler(console_handler)

    # File Handler (always JSON for parsing)
    if settings.LOG_FILE:
        try:
            file_handler = logging.FileHandler(settings.LOG_FILE)
            file_handler.setLevel(logging.INFO)  # File always gets INFO and above

            # Always use JSON for file logs
            json_formatter = CustomJsonFormatter(
                "%(timestamp)s %(level)s %(name)s %(message)s"
            )
            file_handler.setFormatter(json_formatter)

            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            root_logger.warning(f"Could not create file handler: {e}")

    # Set specific logger levels
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Log startup message
    root_logger.info(
        f"Logging configured - Level: {settings.LOG_LEVEL}, Format: {settings.LOG_FORMAT}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Example usage and convenience functions
def log_request(logger: logging.Logger, method: str, path: str, status_code: int, duration: float) -> None:
    """Log HTTP request with structured data"""
    logger.info(
        "HTTP request",
        extra={
            "request_method": method,
            "request_path": path,
            "response_status": status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )


def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None) -> None:
    """Log error with context"""
    logger.error(
        f"Error: {str(error)}",
        exc_info=True,
        extra=context or {},
    )


def log_llm_request(
    logger: logging.Logger,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration: float,
) -> None:
    """Log LLM API request"""
    logger.info(
        "LLM request",
        extra={
            "llm_model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "duration_s": round(duration, 2),
        },
    )


# Initialize logging when module is imported
setup_logging()