"""Script to update track details from Grounded Labs."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from custom_components.oasis_mini.pyoasismini import OasisMini
from custom_components.oasis_mini.pyoasismini.const import TRACKS

ACCESS_TOKEN = os.getenv("GROUNDED_TOKEN")


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
            or result["name"] != TRACKS[track_id].get("name")
            or result["image"] != TRACKS[track_id].get("image")
        ):
            print(f"Updating track {track_id}: {result["name"]}")
            track_info = await client.async_cloud_get_track_info(int(track_id))
            if not track_info:
                print("No track info")
                break
            author = (result.get("author") or {}).get("user") or {}
            updated_tracks[track_id] = {
                "id": track_id,
                "name": result["name"],
                "author": author.get("name") or author.get("nickname") or "Oasis Mini",
                "image": result["image"],
                "clean_pattern": track_info.get("cleanPattern", {}).get("id"),
                "reduced_svg_content": track_info.get("reduced_svg_content"),
            }
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
