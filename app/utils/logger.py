"""
Logging configuration for BioLab Workbench.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import config


def setup_logging(app=None):
    """Configure logging for the application."""
    # Ensure log directory exists
    try:
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        log_dir_available = True
    except (PermissionError, OSError):
        log_dir_available = False

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get loggers
    app_logger = logging.getLogger('biolab.app')
    app_logger.setLevel(logging.INFO)
    
    # Log availability of log directory right after logger is created
    app_logger.info(f"log_dir_available: {log_dir_available}")

    tools_logger = logging.getLogger('biolab.tools')
    tools_logger.setLevel(logging.DEBUG)

    if log_dir_available:
        # Application logger
        app_log_file = os.path.join(config.LOGS_DIR, 'app.log')
        app_handler = RotatingFileHandler(
            app_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)
        app_logger.addHandler(app_handler)

        # Tools logger
        tools_log_file = os.path.join(config.LOGS_DIR, 'tools.log')
        tools_handler = RotatingFileHandler(
            tools_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        tools_handler.setFormatter(formatter)
        tools_handler.setLevel(logging.DEBUG)
        tools_logger.addHandler(tools_handler)

    # Add console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    if not app_logger.handlers:
        app_logger.addHandler(console_handler)
    if not tools_logger.handlers:
        tools_logger.addHandler(console_handler)

    if app:
        app.logger.handlers = app_logger.handlers
        app.logger.setLevel(logging.INFO)

    return app_logger, tools_logger


def get_app_logger():
    """Get the application logger."""
    return logging.getLogger('biolab.app')


def get_tools_logger():
    """Get the tools logger."""
    return logging.getLogger('biolab.tools')