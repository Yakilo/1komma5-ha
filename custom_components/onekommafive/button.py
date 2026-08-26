"""Button platform for the 1KOMMA5° integration (EV quick charge and controls)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OneKomma5ConfigEntry
from .entity import OneKomma5EVEntity, apply_stable_entity_ids

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OneKomma5EVButtonDescription(ButtonEntityDescription):
    """Button entity description for EV quick actions."""

    press_fn: Callable[[Any], Any]


EV_BUTTONS: tuple[OneKomma5EVButtonDescription, ...] = (
    OneKomma5EVButtonDescription(
        key="start_quick_charge",
        translation_key="ev_start_quick_charge",
        icon="mdi:lightning-bolt",
        press_fn=lambda ev: ev.set_charging_mode("QUICK_CHARGE"),
    ),
    OneKomma5EVButtonDescription(
        key="start_solar_charge",
        translation_key="ev_start_solar_charge",
        icon="mdi:solar-power",
        press_fn=lambda ev: ev.set_charging_mode("SOLAR_CHARGE"),
    ),
    OneKomma5EVButtonDescription(
        key="start_smart_charge",
        translation_key="ev_start_smart_charge",
        icon="mdi:auto-fix",
        press_fn=lambda ev: ev.set_charging_mode(
            "PROGRAM_CHARGE" if getattr(ev, "_is_site_asset", False) else "SMART_CHARGE"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OneKomma5ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    data = entry.runtime_data
    live_coordinator = data.live_coordinator
    system_id = data.system.id()
    system_name = data.system_name

    entities: list[ButtonEntity] = []

    if live_coordinator.data:
        for ev in live_coordinator.data.ev_chargers:
            entities.extend(
                OneKomma5EVButton(live_coordinator, system_id, system_name, ev, desc)
                for desc in EV_BUTTONS
            )

    apply_stable_entity_ids(entities, BUTTON_DOMAIN)
    async_add_entities(entities)


class OneKomma5EVButton(OneKomma5EVEntity, ButtonEntity):
    """Button entity for EV actions."""

    entity_description: OneKomma5EVButtonDescription

    def __init__(
        self,
        coordinator: Any,
        system_id: str,
        system_name: str,
        ev: Any,
        description: OneKomma5EVButtonDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, system_id, system_name, ev, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle button press."""
        ev = self._get_ev()
        if ev is None:
            _LOGGER.warning(
                "EV %s not found, cannot press %s",
                self._ev_id,
                self.entity_description.key,
            )
            return
        await self.hass.async_add_executor_job(self.entity_description.press_fn, ev)
        await self.coordinator.async_request_refresh()
