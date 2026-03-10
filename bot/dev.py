from __future__ import annotations

import os
from pathlib import Path

from watchfiles import DefaultFilter, run_process


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_bot() -> None:
    """
    Target function for watchfiles.

    Must be top-level (picklable) on Windows.
    """

    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    # Ensure imports see the project root so "bot" is a proper package.
    os.chdir(PROJECT_ROOT)

    # Import inside the child process
    from bot.main import main

    main()


def _main() -> None:
    """
    Dev runner with auto-restart on file changes.

    Usage:
      python -m bot.dev
    """

    # Watch the bot/ package folder for changes, but run from project root.
    root = PROJECT_ROOT / "bot"
    # Ignore bot/data changes so JSON config updates don't restart the bot.
    watch_filter = DefaultFilter(ignore_dirs=("data",))
    run_process(str(root), target=run_bot, watch_filter=watch_filter)


if __name__ == "__main__":
    _main()

