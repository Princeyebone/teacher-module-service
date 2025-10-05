# logger.py
import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from config import settings

def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Main application logger
    logger = logging.getLogger("tmdl")
    logger.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler (rotating)
    file_handler = RotatingFileHandler(
        log_dir / "tmdl.log",
        maxBytes=1024*1024,  # 1MB
        backupCount=5,
        encoding='utf-8'  # Add UTF-8 encoding to handle emojis and special characters
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logging when module is imported
logger = setup_logging()