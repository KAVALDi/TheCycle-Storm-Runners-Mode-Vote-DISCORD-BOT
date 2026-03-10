from __future__ import annotations

from pathlib import Path
import logging

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROJECT_DIR = BASE_DIR.parent


def find_secret_env() -> Path:
    """
    Locate the secret.env file.

    Priority:
    1) A file named 'secret.env' directly under PROJECT_DIR (repository root).
    2) Any other 'secret.env' inside the project directory (recursive search).
    3) Fallback to the historical location one level above PROJECT_DIR.
    """
    candidates: list[Path] = []

    # 1. Direct secret.env in the project root (preferred).
    root_secret = PROJECT_DIR / "secret.env"
    if root_secret.is_file():
        candidates.append(root_secret)

    # 2. Any other secret.env under PROJECT_DIR (BOT/ and below).
    try:
        for p in PROJECT_DIR.rglob("secret.env"):
            if p != root_secret and p.is_file():
                candidates.append(p)
    except Exception:
        # In worst case, ignore search errors and use fallback.
        pass

    if candidates:
        if len(candidates) > 1:
            logging.getLogger("bot.config").warning(
                "Multiple secret.env files found, using %s. Others: %s",
                candidates[0],
                ", ".join(str(p) for p in candidates[1:]),
            )
        return candidates[0]

    # 3. Fallback: parent of PROJECT_DIR (original behavior).
    return PROJECT_DIR.parent / "secret.env"

# JSON data files
USERS_JSON = DATA_DIR / "users.json"
LOBBY_JSON = DATA_DIR / "lobby.json"
READY_CONFIG_JSON = DATA_DIR / "ready_config.json"
SIMULATE_CONFIG_JSON = DATA_DIR / "simulate_config.json"
ADMIN_ACCESS_JSON = DATA_DIR / "admin_access.json"
UI_STYLE_JSON = DATA_DIR / "ui_style.json"
ALLOWED_GUILDS_JSON = DATA_DIR / "allowed_guilds.json"

# Other constants
FAKE_ID_BASE = 10_000_000

# No permission required info
REPO_URL = "https://github.com/KAVALDi/TheCycle-Storm-Runners-Mode-Vote-DISCORD-BOT"