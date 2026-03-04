"""Shared global state for CLI output mode."""

JSON_MODE: bool = False


def get_json_mode() -> bool:
    return JSON_MODE


def set_json_mode(value: bool) -> None:
    global JSON_MODE  # noqa: PLW0603
    JSON_MODE = value
