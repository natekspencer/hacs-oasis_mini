"""Constants."""

from __future__ import annotations

import json
import os
from typing import Final

__TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
with open(__TRACKS_FILE, "r", encoding="utf8") as file:
    TRACKS: Final[dict[int, dict[str, str]]] = json.load(file)
