from loguru import logger
import sys


def configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | {message} | {extra}",
        level="INFO",
        serialize=True,
    )
