"""Simple execution sandbox for strategy functions.

Provides timeout-guarded execution and memory usage monitoring.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Tuple


class SandboxError(Exception):
    """Raised when a sandboxed operation fails (timeout, resource limit, etc.)."""


def run_with_timeout(
    func: Callable[..., Any],
    args: Tuple[Any, ...] = (),
    timeout_sec: float = 30,
) -> Any:
    """Execute *func(*args)* in a daemon thread with a timeout.

    Parameters
    ----------
    func:
        The callable to execute.
    args:
        Positional arguments forwarded to *func*.
    timeout_sec:
        Maximum wall-clock seconds to wait.  Defaults to 30.

    Returns
    -------
    The return value of *func*.

    Raises
    ------
    SandboxError
        If the function does not finish within *timeout_sec* or raises an
        exception.
    """
    result_holder: list = []
    error_holder: list = []

    def _target() -> None:
        try:
            result_holder.append(func(*args))
        except Exception as exc:  # noqa: BLE001
            error_holder.append(exc)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        raise SandboxError(
            f"Function '{func.__name__}' did not complete within {timeout_sec}s"
        )

    if error_holder:
        raise SandboxError(
            f"Function '{func.__name__}' raised an exception: {error_holder[0]}"
        ) from error_holder[0]

    if not result_holder:
        # Function returned None (valid) or something unexpected happened
        return None

    return result_holder[0]


def check_memory_usage() -> float:
    """Return the current process RSS memory usage in megabytes.

    Uses ``/proc/self/status`` on Linux and ``resource.getrusage`` as a
    cross-platform fallback (macOS reports in bytes, Linux in KB).
    """
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # macOS returns bytes; Linux returns KB
        if os.uname().sysname == "Darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except Exception:  # noqa: BLE001
        return 0.0
