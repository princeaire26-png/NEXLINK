"""
Logging configuration for NEXLINK backend.

Uses structlog for structured, JSON-formatted logging.
"""

import logging
import sys
import structlog
from app.core.config import get_settings


def setup_logging():
    """
    Configure structured logging with structlog.
    
    In development: Pretty-printed output
    In production: JSON-formatted output
    """
    settings = get_settings()
    
    # Determine if we should use pretty printing
    pretty_print = settings.app_env == "development"
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if pretty_print:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False
    )
    
    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level
    )
