import os
import logging
from db_logger import MongoQueueHandler


def setup_logging():
    env = os.getenv("ENVIRONMENT", "production").lower()

    # Root logger
    logger = logging.getLogger()
    logger.handlers.clear()

    # Decide log level
    if env == "testing":
        log_level = logging.DEBUG   # log everything
    else:
        log_level = logging.ERROR   # only errors

    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # Mongo handler
    mongo_handler = MongoQueueHandler()
    mongo_handler.setLevel(log_level)
    mongo_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # Attach handlers
    logger.addHandler(console_handler)
    if not any(isinstance(h, MongoQueueHandler) for h in logger.handlers):
        logger.addHandler(mongo_handler)
    
    return logger