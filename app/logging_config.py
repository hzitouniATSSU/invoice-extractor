import logging

from app.config import LOG_LEVEL


def configure_logging(level=LOG_LEVEL):
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
