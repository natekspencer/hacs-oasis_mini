"""Support for media browsing/searching."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
    SearchError,
    SearchMedia,
    SearchMediaQuery,
)

from .pyoasiscontrol import OasisCloudClient
from .pyoasiscontrol.const import TRACKS
from .pyoasiscontrol.utils import get_image_url_from_track, get_track_ids_from_playlist

_LOGGER = logging.getLogger(__name__)

MEDIA_TYPE_OASIS_ROOT = "oasis_library"
MEDIA_TYPE_OASIS_PLAYLISTS = "oasis_playlists"
MEDIA_TYPE_OASIS_PLAYLIST = MediaType.PLAYLIST
MEDIA_TYPE_OASIS_TRACKS = "oasis_tracks"
MEDIA_TYPE_OASIS_TRACK = MediaType.TRACK


async def build_root_response() -> BrowseMedia:
    """Top-level library node that exposes Tracks and Playlists."""
    children = [
        BrowseMedia(
            title="Playlists",
            media_class=MediaClass.DIRECTORY,
            media_content_id="playlists_root",
            media_content_type=MEDIA_TYPE_OASIS_PLAYLISTS,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.PLAYLIST,
        ),
        BrowseMedia(
            title="Tracks",
            media_class=MediaClass.DIRECTORY,
            media_content_id="tracks_root",
            media_content_type=MEDIA_TYPE_OASIS_TRACKS,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
        ),
    ]

    return BrowseMedia(
        title="Oasis Library",
        media_class=MediaClass.DIRECTORY,
        media_content_id="oasis_root",
        media_content_type=MEDIA_TYPE_OASIS_ROOT,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MediaClass.DIRECTORY,
    )


async def build_playlists_root(cloud: OasisCloudClient) -> BrowseMedia:
    """Build the 'Playlists' directory from the cloud playlists cache."""
    playlists = await cloud.async_get_playlists(personal_only=False)

    children = [
        BrowseMedia(
            title=playlist.get("name") or f"Playlist #{playlist['id']}",
            media_class=MediaClass.PLAYLIST,
            media_content_id=str(playlist["id"]),
            media_content_type=MEDIA_TYPE_OASIS_PLAYLIST,
            can_play=True,
            can_expand=True,
            thumbnail=get_first_image_for_playlist(playlist),
        )
        for playlist in playlists
        if "id" in playlist
    ]

    return BrowseMedia(
        title="Playlists",
        media_class=MediaClass.DIRECTORY,
        media_content_id="playlists_root",
        media_content_type=MEDIA_TYPE_OASIS_PLAYLISTS,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MediaClass.PLAYLIST,
    )


async def build_playlist_item(cloud: OasisCloudClient, playlist_id: int) -> BrowseMedia:
    """Build a single playlist node including its track children."""
    playlists = await cloud.async_get_playlists(personal_only=False)
    playlist = next((p for p in playlists if p.get("id") == playlist_id), None)
    if not playlist:
        raise BrowseError(f"Unknown playlist id: {playlist_id}")

    title = playlist.get("name") or f"Playlist #{playlist_id}"

    track_ids = get_track_ids_from_playlist(playlist)
    children = [build_track_item(track_id) for track_id in track_ids]

    return BrowseMedia(
        title=title,
        media_class=MediaClass.PLAYLIST,
        media_content_id=str(playlist_id),
        media_content_type=MEDIA_TYPE_OASIS_PLAYLIST,
        can_play=True,
        can_expand=True,
        children=children,
        children_media_class=MediaClass.IMAGE,
        thumbnail=get_first_image_for_playlist(playlist),
    )


def build_tracks_root() -> BrowseMedia:
    """Build the 'Tracks' directory based on the TRACKS mapping."""
    children = [
        BrowseMedia(
            title=meta.get("name") or f"Track #{track_id}",
            media_class=MediaClass.IMAGE,
            media_content_id=str(track_id),
            media_content_type=MEDIA_TYPE_OASIS_TRACK,
            can_play=True,
            can_expand=False,
            thumbnail=get_image_url_from_track(meta),
        )
        for track_id, meta in TRACKS.items()
    ]

    return BrowseMedia(
        title="Tracks",
        media_class=MediaClass.DIRECTORY,
        media_content_id="tracks_root",
        media_content_type=MEDIA_TYPE_OASIS_TRACKS,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MediaClass.IMAGE,
    )


def build_track_item(track_id: int) -> BrowseMedia:
    """Build a single track node for a given track id."""
    meta = TRACKS.get(track_id) or {}

    return BrowseMedia(
        title=meta.get("name") or f"Track #{track_id}",
        media_class=MediaClass.IMAGE,
        media_content_id=str(track_id),
        media_content_type=MEDIA_TYPE_OASIS_TRACK,
        can_play=True,
        can_expand=False,
        thumbnail=get_image_url_from_track(meta),
    )


def get_first_image_for_playlist(playlist: dict[str, Any]) -> str | None:
    """Get the first image from a playlist dictionary."""
    for track in playlist.get("patterns") or []:
        if image := get_image_url_from_track(track):
            return image
    return None


async def async_search_media(
    cloud: OasisCloudClient,
    query: SearchMediaQuery,
) -> SearchMedia:
    """
    Search tracks and/or playlists and return a SearchMedia result.

    - If media_type == MEDIA_TYPE_OASIS_TRACK:   search tracks only
    - If media_type == MEDIA_TYPE_OASIS_PLAYLIST: search playlists only
    - Otherwise: search both tracks and playlists
    """
    try:
        search_query = (query.search_query or "").strip().lower()

        search_tracks = query.media_content_type in (
            None,
            "",
            MEDIA_TYPE_OASIS_ROOT,
            MEDIA_TYPE_OASIS_TRACKS,
            MEDIA_TYPE_OASIS_TRACK,
        )
        search_playlists = query.media_content_type in (
            None,
            "",
            MEDIA_TYPE_OASIS_ROOT,
            MEDIA_TYPE_OASIS_PLAYLISTS,
            MEDIA_TYPE_OASIS_PLAYLIST,
        )

        track_children: list[BrowseMedia] = []
        playlist_children: list[BrowseMedia] = []

        if search_tracks:
            for track_id, meta in TRACKS.items():
                name = (meta.get("name") or "").lower()

                haystack = name.strip()
                if search_query in haystack:
                    track_children.append(build_track_item(track_id))

        if search_playlists:
            playlists = await cloud.async_get_playlists(personal_only=False)

            for pl in playlists:
                playlist_id = pl.get("id")
                if playlist_id is None:
                    continue

                name = (pl.get("name") or "").lower()
                if search_query not in name:
                    continue

                playlist_children.append(
                    BrowseMedia(
                        title=pl.get("name") or f"Playlist #{playlist_id}",
                        media_class=MediaClass.PLAYLIST,
                        media_content_id=str(playlist_id),
                        media_content_type=MEDIA_TYPE_OASIS_PLAYLIST,
                        can_play=True,
                        can_expand=True,
                        thumbnail=get_first_image_for_playlist(pl),
                    )
                )

        root = BrowseMedia(
            title=f"Search results for '{query.search_query}'",
            media_class=MediaClass.DIRECTORY,
            media_content_id=f"search:{query.search_query}",
            media_content_type=MEDIA_TYPE_OASIS_ROOT,
            can_play=False,
            can_expand=True,
            children=[],
        )

        if playlist_children and not track_children:
            root.children_media_class = MediaClass.PLAYLIST
        else:
            root.children_media_class = MediaClass.IMAGE

        root.children.extend(playlist_children)
        root.children.extend(track_children)

        return SearchMedia(result=root)

    except Exception as err:
        _LOGGER.debug(
            "Search error details for %s: %s", query.search_query, err, exc_info=True
        )
        raise SearchError(f"Error searching for {query.search_query}") from err
