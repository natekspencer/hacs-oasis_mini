"""Constants."""

from __future__ import annotations

import json
import os
from typing import Any, Final

__TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
try:
    with open(__TRACKS_FILE, "r", encoding="utf8") as file:
        TRACKS: Final[dict[int, dict[str, Any]]] = {
            int(k): v for k, v in json.load(file).items()
        }
except Exception:  # ignore: broad-except
    TRACKS = {}
