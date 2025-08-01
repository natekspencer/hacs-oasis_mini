"""Script to update track details from Grounded Labs."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from custom_components.oasis_mini.pyoasismini import OasisMini
from custom_components.oasis_mini.pyoasismini.const import TRACKS

ACCESS_TOKEN = os.getenv("GROUNDED_TOKEN")


def get_author_name(data: dict) -> str:
    """Get author name from a dict."""
    author = (data.get("author") or {}).get("user") or {}
    return author.get("name") or author.get("nickname") or "Oasis Mini"


async def update_tracks() -> None:
    """Update tracks."""
    client = OasisMini("", ACCESS_TOKEN)

    try:
        data = await client.async_cloud_get_tracks()
    except Exception as ex:
        print(type(ex).__name__, ex)
        await client.session.close()
        return

    if not isinstance(data, list):
        print("Unexpected result:", data)
        return

    updated_tracks: dict[int, dict[str, Any]] = {}
    for result in filter(lambda d: d["public"], data):
        if (
            (track_id := result["id"]) not in TRACKS
            or any(
                result[field] != TRACKS[track_id].get(field)
                for field in ("name", "image", "png_image")
            )
            or TRACKS[track_id].get("author") != get_author_name(result)
        ):
            print(f"Updating track {track_id}: {result['name']}")
            track_info = await client.async_cloud_get_track_info(int(track_id))
            if not track_info:
                print("No track info")
                break
            result["author"] = get_author_name(result)
            result["reduced_svg_content_new"] = track_info.get(
                "reduced_svg_content_new"
            )
            updated_tracks[track_id] = result
    await client.session.close()

    if not updated_tracks:
        print("No updated tracks")
        return

    tracks = {k: v for k, v in TRACKS.items() if k in map(lambda d: d["id"], data)}
    tracks.update(updated_tracks)
    tracks = dict(sorted(tracks.items(), key=lambda t: t[1]["name"].lower()))

    with open(
        "custom_components/oasis_mini/pyoasismini/tracks.json", "w", encoding="utf8"
    ) as file:
        json.dump(tracks, file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(update_tracks())
