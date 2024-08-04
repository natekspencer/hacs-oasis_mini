# """Oasis Mini switch entity."""

# from __future__ import annotations

# from typing import Any

# from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
# from homeassistant.core import HomeAssistant
# from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from . import OasisMiniConfigEntry
# from .entity import OasisMiniEntity


# async def async_setup_entry(
#     hass: HomeAssistant,
#     entry: OasisMiniConfigEntry,
#     async_add_entities: AddEntitiesCallback,
# ) -> None:
#     """Set up Oasis Mini switchs using config entry."""
#     async_add_entities(
#         [
#             OasisMiniSwitchEntity(entry.runtime_data, descriptor)
#             for descriptor in DESCRIPTORS
#         ]
#     )


# class OasisMiniSwitchEntity(OasisMiniEntity, SwitchEntity):
#     """Oasis Mini switch entity."""

#     @property
#     def is_on(self) -> bool:
#         """Return True if entity is on."""
#         return int(getattr(self.device, self.entity_description.key))

#     async def async_turn_off(self, **kwargs: Any) -> None:
#         """Turn the entity off."""
#         await self.device.async_set_repeat_playlist(False)
#         await self.coordinator.async_request_refresh()

#     async def async_turn_on(self, **kwargs: Any) -> None:
#         """Turn the entity on."""
#         await self.device.async_set_repeat_playlist(True)
#         await self.coordinator.async_request_refresh()


# DESCRIPTORS = {
#     SwitchEntityDescription(
#         key="repeat_playlist",
#         name="Repeat playlist",
#     ),
# }
