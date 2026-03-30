import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger with the given name.
    Sets up a stream handler to stdout and a timed rotating file handler
    on the root logger if not already configured.
    """
    # Use the root logger to handle all log messages from any module
    root_logger = logging.getLogger()
    
    if not root_logger.handlers:
        root_logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Filename will be dateoftoday.log
        # We use a base filename and set up TimedRotatingFileHandler to rotate daily.
        # To strictly match "dateoftoday.log", we can use a base name and let it rotate.
        # However, a common pattern for "dateoftoday.log" is to have the current file
        # named with the date. 
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"{today}.log")
        
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
    return logging.getLogger(name)
