"""Separate once-reserved sixty-session validation experiment."""

from .holding_cli import main

if __name__ == "__main__":
    raise SystemExit(main(profile="validation60"))
