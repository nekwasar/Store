import logging
import sys

_formatter = logging.Formatter(
    '{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S',
)

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_formatter)

logger = logging.getLogger("fastapi_shop")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)


def get_logger(name: str) -> logging.Logger:
    child = logger.getChild(name)
    if not child.handlers:
        child.handlers = logger.handlers
        child.setLevel(logger.level)
    return child
