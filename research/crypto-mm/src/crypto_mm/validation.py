"""Shared validation for discrete nanosecond and sample-count settings."""


def require_integer(name: str, value: int, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
