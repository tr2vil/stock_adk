"""
Structured logging configuration using structlog.

LOG_FORMAT 환경변수로 출력 형식을 제어:
  - "console" (기본): 컬러 콘솔 출력 (로컬 개발용)
  - "json": JSON 한 줄 출력 (Docker/Loki 수집용)
"""
import logging
import os
import sys
import structlog


def setup_logging(level: str = "INFO"):
    """Configure structured logging for the application."""

    log_format = os.getenv("LOG_FORMAT", "console").lower()

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    # Shared processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Choose renderer based on LOG_FORMAT
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Initialize logging on import
setup_logging()
