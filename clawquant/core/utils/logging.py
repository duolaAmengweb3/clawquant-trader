"""Logging configuration using Rich console handler."""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

_CONFIGURED = False
_CONSOLE = Console(stderr=True)


def setup_logging(verbose: bool = False) -> None:
    """Configure the root logger with a Rich console handler.

    Parameters
    ----------
    verbose:
        If ``True``, set level to ``DEBUG``; otherwise ``INFO``.
    """
    global _CONFIGURED  # noqa: PLW0603

    if _CONFIGURED:
        return

    level = logging.DEBUG if verbose else logging.INFO

    handler = RichHandler(
        console=_CONSOLE,
        show_time=True,
        show_path=verbose,
        rich_tracebacks=True,
        tracebacks_show_locals=verbose,
        markup=True,
    )
    handler.setLevel(level)

    fmt = logging.Formatter("%(message)s", datefmt="[%X]")
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging is configured.

    Parameters
    ----------
    name:
        Logger name, typically ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
    """
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
