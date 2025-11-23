"""Oasis cloud client."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientResponseError, ClientSession

from ..exceptions import UnauthenticatedError
from ..utils import now

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://app.grounded.so"
PLAYLISTS_REFRESH_LIMITER = timedelta(minutes=5)
SOFTWARE_REFRESH_LIMITER = timedelta(hours=1)


class OasisCloudClient:
    """Cloud client for Oasis.

    Responsibilities:
    - Manage aiohttp session (optionally owned)
    - Manage access token
    - Provide async_* helpers for:
        * login/logout
        * user info
        * devices
        * tracks/playlists
        * latest software metadata
    """

    def __init__(
        self,
        *,
        session: ClientSession | None = None,
        access_token: str | None = None,
    ) -> None:
        self._session = session
        self._owns_session = session is None
        self._access_token = access_token

        # playlists cache
        self.playlists: list[dict[str, Any]] = []
        self._playlists_next_refresh = now()
        self._playlists_lock = asyncio.Lock()

        self._playlist_details: dict[int, dict[str, str]] = {}

        # software metadata cache
        self._software_details: dict[str, int | str] | None = None
        self._software_next_refresh = now()
        self._software_lock = asyncio.Lock()

    @property
    def session(self) -> ClientSession:
        """Return (or lazily create) the aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = ClientSession()
            self._owns_session = True
        return self._session

    async def async_close(self) -> None:
        """Close owned session (call from HA unload / cleanup)."""
        if self._session and not self._session.closed and self._owns_session:
            await self._session.close()

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        self._access_token = value

    async def async_login(self, email: str, password: str) -> None:
        """Login via the cloud and store the access token."""
        response = await self._async_request(
            "POST",
            urljoin(BASE_URL, "api/auth/login"),
            json={"email": email, "password": password},
        )
        token = response.get("access_token") if isinstance(response, dict) else None
        self.access_token = token
        _LOGGER.debug("Cloud login succeeded, token set: %s", bool(token))

    async def async_logout(self) -> None:
        """Logout from the cloud."""
        await self._async_auth_request("GET", "api/auth/logout")
        self.access_token = None

    async def async_get_user(self) -> dict:
        """Get current user info."""
        return await self._async_auth_request("GET", "api/auth/user")

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Get user devices (raw JSON from API)."""
        return await self._async_auth_request("GET", "api/user/devices")

    async def async_get_playlists(
        self, personal_only: bool = False
    ) -> list[dict[str, Any]]:
        """Get playlists from the cloud (cached by PLAYLISTS_REFRESH_LIMITER)."""
        now_dt = now()

        def _is_cache_valid() -> bool:
            return self._playlists_next_refresh > now_dt and bool(self.playlists)

        if _is_cache_valid():
            return self.playlists

        async with self._playlists_lock:
            # Double-check in case another task just refreshed it
            now_dt = now()
            if _is_cache_valid():
                return self.playlists

            params = {"my_playlists": str(personal_only).lower()}
            playlists = await self._async_auth_request(
                "GET", "api/playlist", params=params
            )

            if not isinstance(playlists, list):
                playlists = []

            self.playlists = playlists
            self._playlists_next_refresh = now_dt + PLAYLISTS_REFRESH_LIMITER

            return self.playlists

    async def async_get_track_info(self, track_id: int) -> dict[str, Any] | None:
        """Get single track info from the cloud."""
        try:
            return await self._async_auth_request("GET", f"api/track/{track_id}")
        except ClientResponseError as err:
            if err.status == 404:
                return {"id": track_id, "name": f"Unknown Title (#{track_id})"}
        except Exception as ex:  # noqa: BLE001
            _LOGGER.exception("Error fetching track %s: %s", track_id, ex)
        return None

    async def async_get_tracks(
        self, tracks: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """Get multiple tracks info from the cloud (handles pagination)."""
        response = await self._async_auth_request(
            "GET",
            "api/track",
            params={"ids[]": tracks or []},
        )
        if not response:
            return []
        track_details = response.get("data", [])
        while next_page_url := response.get("next_page_url"):
            response = await self._async_auth_request("GET", next_page_url)
            track_details += response.get("data", [])
        return track_details

    async def async_get_latest_software_details(
        self, *, force_refresh: bool = False
    ) -> dict[str, int | str] | None:
        """Get latest software metadata from cloud (cached)."""
        now_dt = now()

        def _is_cache_valid() -> bool:
            return (
                not force_refresh
                and self._software_details is not None
                and self._software_next_refresh > now_dt
            )

        if _is_cache_valid():
            return self._software_details

        async with self._software_lock:
            # Double-check in case another task just refreshed it
            now_dt = now()
            if _is_cache_valid():
                return self._software_details

            details = await self._async_auth_request("GET", "api/software/last-version")

            if not isinstance(details, dict):
                details = {}

            self._software_details = details
            self._software_next_refresh = now_dt + SOFTWARE_REFRESH_LIMITER

            return self._software_details

    async def _async_auth_request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform an authenticated cloud request."""
        if not self.access_token:
            raise UnauthenticatedError("Unauthenticated")

        headers = kwargs.pop("headers", {}) or {}
        headers["Authorization"] = f"Bearer {self.access_token}"

        return await self._async_request(
            method,
            url if url.startswith("http") else urljoin(BASE_URL, url),
            headers=headers,
            **kwargs,
        )

    async def _async_request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Low-level HTTP helper for both cloud and (if desired) device HTTP."""
        session = self.session
        _LOGGER.debug(
            "%s %s",
            method,
            session._build_url(url).update_query(  # pylint: disable=protected-access
                kwargs.get("params"),
            ),
        )
        response = await session.request(method, url, **kwargs)

        if response.status == 200:
            if response.content_type == "application/json":
                return await response.json()
            if response.content_type == "text/plain":
                return await response.text()
            if response.content_type == "text/html" and BASE_URL in url:
                text = await response.text()
                if "login-page" in text:
                    raise UnauthenticatedError("Unauthenticated")
            return None

        if response.status == 401:
            raise UnauthenticatedError("Unauthenticated")

        response.raise_for_status()
