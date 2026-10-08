import logging


def configure_logging() -> None:
    """Configure application logging without logging settings or request bodies."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
