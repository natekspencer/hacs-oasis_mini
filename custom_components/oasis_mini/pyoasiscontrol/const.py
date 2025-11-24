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
except (FileNotFoundError, json.JSONDecodeError, OSError):
    TRACKS = {}

AUTOPLAY_MAP: Final[dict[str, str]] = {
    "1": "Off",  # display off (disabled) first
    "0": "Immediately",
    "2": "After 5 minutes",
    "3": "After 10 minutes",
    "4": "After 30 minutes",
    "6": "After 1 hour",
    "7": "After 6 hours",
    "8": "After 12 hours",
    "5": "After 24 hours",  # purposefully placed so time is incrementally displayed
}

ERROR_CODE_MAP: Final[dict[int, str]] = {
    0: "None",
    1: "Error has occurred while reading the flash memory",
    2: "Error while starting the Wifi",
    3: "Error when starting DNS settings for your machine",
    4: "Failed to open the file to write",
    5: "Not enough memory to perform the upgrade",
    6: "Error while trying to upgrade your system",
    7: "Error while trying to download the new version of the software",
    8: "Error while reading the upgrading file",
    9: "Failed to start downloading the upgrade file",
    10: "Error while starting downloading the job file",
    11: "Error while opening the file folder",
    12: "Failed to delete a file",
    13: "Error while opening the job file",
    14: "You have wrong power adapter",
    15: "Failed to update the device IP on Oasis Server",
    16: "Your device failed centering itself",
    17: "There appears to be an issue with your Oasis Device",
    18: "Error while downloading the job file",
}

LED_EFFECTS: Final[dict[str, str]] = {
    "0": "Solid",
    "1": "Rainbow",
    "2": "Glitter",
    "3": "Confetti",
    "4": "Sinelon",
    "5": "BPM",
    "6": "Juggle",
    "7": "Theater",
    "8": "Color Wipe",
    "9": "Sparkle",
    "10": "Comet",
    "11": "Follow Ball",
    "12": "Follow Rainbow",
    "13": "Chasing Comet",
    "14": "Gradient Follow",
    "15": "Cumulative Fill",
    "16": "Multi Comets A",
    "17": "Rainbow Chaser",
    "18": "Twinkle Lights",
    "19": "Tennis Game",
    "20": "Breathing Exercise 4-7-8",
    "21": "Cylon Scanner",
    "22": "Palette Mode",
    "23": "Aurora Flow",
    "24": "Colorful Drops",
    "25": "Color Snake",
    "26": "Flickering Candles",
    "27": "Digital Rain",
    "28": "Center Explosion",
    "29": "Rainbow Plasma",
    "30": "Comet Race",
    "31": "Color Waves",
    "32": "Meteor Storm",
    "33": "Firefly Flicker",
    "34": "Ripple",
    "35": "Jelly Bean",
    "36": "Forest Rain",
    "37": "Multi Comets",
    "38": "Multi Comets with Background",
    "39": "Rainbow Fill",
    "40": "White Red Comet",
    "41": "Color Comets",
}

STATUS_BOOTING: Final[int] = 0
STATUS_STOPPED: Final[int] = 2
STATUS_CENTERING: Final[int] = 3
STATUS_PLAYING: Final[int] = 4
STATUS_PAUSED: Final[int] = 5
STATUS_SLEEPING: Final[int] = 6
STATUS_ERROR: Final[int] = 9
STATUS_UPDATING: Final[int] = 11
STATUS_DOWNLOADING: Final[int] = 13
STATUS_BUSY: Final[int] = 14
STATUS_LIVE: Final[int] = 15

STATUS_CODE_MAP: Final[dict[int, str]] = {
    STATUS_BOOTING: "booting",
    STATUS_STOPPED: "stopped",
    STATUS_CENTERING: "centering",
    STATUS_PLAYING: "playing",
    STATUS_PAUSED: "paused",
    STATUS_SLEEPING: "sleeping",
    STATUS_ERROR: "error",
    STATUS_UPDATING: "updating",
    STATUS_DOWNLOADING: "downloading",
    STATUS_BUSY: "busy",
    STATUS_LIVE: "live",
}
