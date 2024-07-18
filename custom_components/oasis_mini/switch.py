# """Oasis Mini switch entity."""

# from __future__ import annotations

# from typing import Any

# from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
# from homeassistant.config_entries import ConfigEntry
# from homeassistant.core import HomeAssistant
# from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from .const import DOMAIN
# from .coordinator import OasisMiniCoordinator
# from .entity import OasisMiniEntity


# async def async_setup_entry(
#     hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
# ) -> None:
#     """Set up Oasis Mini switchs using config entry."""
#     coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
#     async_add_entities(
#         [
#             OasisMiniSwitchEntity(coordinator, entry, descriptor)
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
