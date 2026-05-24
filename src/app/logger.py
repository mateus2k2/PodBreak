import logging
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str, log_file: str, level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5,
) -> logging.Logger:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
