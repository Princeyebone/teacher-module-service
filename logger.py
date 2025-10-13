# logger.py
import logging
import logging.handlers
import sys
import os
from pathlib import Path
from config import settings

class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    A RotatingFileHandler that handles PermissionError on Windows
    when trying to rotate log files that are locked by another process.
    """
    def doRollover(self):
        """
        Override doRollover to handle PermissionError gracefully.
        """
        try:
            super().doRollover()
        except PermissionError:
            # If we can't rotate the file, just continue logging to the same file
            # This can happen on Windows when the file is locked by another process
            pass
        except OSError as e:
            # Handle other OS errors that might occur during rotation
            if e.errno != 32:  # Only suppress "file in use" errors
                raise

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
    
    # File handler (rotating) with error handling for Windows
    file_handler = SafeRotatingFileHandler(
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