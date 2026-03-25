import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger with the given name.
    Sets up a stream handler to stdout if no handlers exist.
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
    return logger
