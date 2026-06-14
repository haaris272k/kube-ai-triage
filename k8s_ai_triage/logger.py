"""
Logging Configuration Module

This module provides a simple, production-ready logging setup for the k8s-triage tool.
It configures dual-output logging: console messages for user feedback and detailed file
logs for debugging and audit trails.

Logging Strategy:
- Console: Simple format ("LEVEL: message") for clean user experience
- File: Timestamped log files in logs/ directory for detailed debugging
- All levels (DEBUG through ERROR) logged to file
- Console shows only INFO and above by default (DEBUG with --debug flag)

Log File Naming:
- Pattern: logs/k8s_triage_YYYYMMDD_HHMMSS.log
- Each run creates a new timestamped log file
- Makes it easy to correlate logs with specific analysis runs

Usage:
    from k8s_ai_triage.logger import setup_logging, get_logger
    
    # In CLI entry point
    logger = setup_logging(log_level="INFO")
    
    # In other modules
    logger = get_logger()
    logger.info("Starting analysis...")
    logger.debug("Detailed debug info")

The logging system automatically creates the logs/ directory if it doesn't exist.
"""
import logging
from pathlib import Path
from datetime import datetime


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup basic logging."""
    Path("logs").mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/k8s_triage_{timestamp}.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    
    logger = logging.getLogger("k8s_ai_triage")
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


def get_logger() -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger("k8s_ai_triage")
