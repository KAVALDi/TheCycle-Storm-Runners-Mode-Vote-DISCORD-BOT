from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except FileNotFoundError:
        return {}
    except Exception:
        log.exception("failed to load json: %s", path)
        return {}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

