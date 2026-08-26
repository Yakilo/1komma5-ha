"""EV adapter supporting both GridX and 1K5 site assets EV models."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class OneKomma5EV:
    """Unified EV model supporting GridX devices/evs and 1K5 site assets/evs."""

    def __init__(self, raw_data: dict[str, Any], system: Any, is_site_asset: bool = False) -> None:
        self._data = raw_data
        self._system = system
        self._is_site_asset = is_site_asset

    def id(self) -> str:
        return self._data["id"]

    def name(self) -> str | None:
        if self._is_site_asset:
            return self._data.get("name")
        return (self._data.get("profile") or {}).get("name")

    def manufacturer(self) -> str | None:
        if self._is_site_asset:
            return self._data.get("manufacturer")
        value = (self._data.get("profile") or {}).get("manufacturer")
        return value.strip() if value else None

    def model(self) -> str | None:
        if self._is_site_asset:
            return self._data.get("model")
        return (self._data.get("profile") or {}).get("model")

    def capacity_wh(self) -> float | None:
        if self._is_site_asset:
            cap = self._data.get("capacity", {})
            val = cap.get("value")
            if val is None:
                return None
            unit = (cap.get("unit") or "kWh").lower()
            return float(val * 1000.0) if "k" in unit else float(val)
        cap = (self._data.get("profile") or {}).get("capacity")
        return float(cap["value"]) if cap else None

    def min_charging_current_a(self) -> float | None:
        if self._is_site_asset:
            return None
        node = (self._data.get("profile") or {}).get("minChargingCurrent")
        return float(node["value"]) if node else None

    def safety_range_km(self) -> float | None:
        if self._is_site_asset:
            return None
        node = (self._data.get("profile") or {}).get("safetyRange")
        return float(node["value"]) if node else None

    def assigned_charger_id(self) -> str | None:
        if self._is_site_asset:
            return self._data.get("chargerId")
        return self._data.get("assignedChargerId")

    def charging_mode_raw(self) -> str:
        if self._is_site_asset:
            return self._data.get("chargingMode") or "QUICK_CHARGE"
        return (self._data.get("chargeSettings") or {}).get("chargingMode") or "QUICK_CHARGE"

    def charging_mode(self) -> Any:
        from onekommafive.models import ChargingMode
        mode_str = self.charging_mode_raw()
        try:
            return ChargingMode(mode_str)
        except (ValueError, KeyError):
            return mode_str

    def default_soc(self) -> float | None:
        if self._is_site_asset:
            return None
        val = (self._data.get("chargeSettings") or {}).get("defaultSoc")
        return float(val * 100) if val is not None else None

    def target_soc(self) -> float | None:
        if self._is_site_asset:
            val = self._data.get("targetSoc")
            return float(val * 100) if val is not None else None
        val = (self._data.get("chargeSettings") or {}).get("targetSoc")
        return float(val * 100) if val is not None else None

    def primary_schedule_days(self) -> list[str]:
        if self._is_site_asset:
            return []
        return (self._data.get("chargeSettings") or {}).get("primaryScheduleDays") or []

    def primary_schedule_departure_time(self) -> str | None:
        if self._is_site_asset:
            return self._data.get("departureTime")
        return (self._data.get("chargeSettings") or {}).get("primaryScheduleDepartureTime")

    def primary_schedule_departure_soc(self) -> float | None:
        if self._is_site_asset:
            val = self._data.get("targetSoc")
            return float(val * 100) if val is not None else None
        val = (self._data.get("chargeSettings") or {}).get("primaryScheduleDepartureSoc")
        return float(val * 100) if val is not None else None

    def current_soc(self) -> float | None:
        if self._is_site_asset:
            latest_soc = self._data.get("latestSoc")
            if latest_soc is not None:
                return float(latest_soc * 100.0)
            manual_soc = self._data.get("manualSoc")
            if manual_soc is not None:
                return float(manual_soc * 100.0)
            return None
        manual_soc = self._data.get("manualSoc")
        if manual_soc is not None:
            return float(manual_soc * 100.0)
        return None

    def _get_client(self) -> Any:
        return getattr(self._system, "_client", getattr(self._system, "client", None))

    def _url(self) -> str:
        client = self._get_client()
        base = (
            getattr(client, "HEARTBEAT_API", "https://heartbeat.1komma5grad.com")
            if client
            else "https://heartbeat.1komma5grad.com"
        )
        if self._is_site_asset:
            return f"{base}/api/v1/sites/{self._system.id()}/assets/evs/{self.id()}"
        return f"{base}/api/v1/systems/{self._system.id()}/devices/evs/{self.id()}"

    def set_charging_mode(self, mode: Any) -> None:
        mode_str = mode.value if hasattr(mode, "value") else str(mode)
        mode_str = mode_str.upper()
        if self.charging_mode_raw() == mode_str:
            return

        client = self._get_client()
        if self._is_site_asset:
            payload = {"chargingMode": mode_str}
        else:
            payload = {"chargeSettings": {"chargingMode": mode_str}}

        if client and hasattr(client, "_request"):
            client._request("PATCH", self._url(), json=payload, error_label="Failed to set charging mode")
        elif client and hasattr(client, "get_token"):
            import requests

            token = client.get_token()
            res = requests.patch(
                self._url(),
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30,
            )
            if res.status_code != 200:
                raise Exception(f"Failed to set charging mode: {res.text}")

        if self._is_site_asset:
            self._data["chargingMode"] = mode_str
        else:
            self._data.setdefault("chargeSettings", {})["chargingMode"] = mode_str

    def set_current_soc(self, soc: float) -> None:
        soc_decimal = float(soc / 100.0) if soc > 0 else 0.0
        client = self._get_client()
        if self._is_site_asset:
            payload = {"manualSoc": soc_decimal}
        else:
            payload = {"id": self.id(), "manualSoc": soc_decimal}

        if client and hasattr(client, "_request"):
            client._request("PATCH", self._url(), json=payload, error_label="Failed to set state of charge")
        elif client and hasattr(client, "get_token"):
            import requests

            token = client.get_token()
            requests.patch(
                self._url(),
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30,
            )

        self._data["manualSoc"] = soc_decimal

    def set_target_soc(self, soc: float) -> None:
        soc_decimal = float(soc / 100.0) if soc > 0 else 0.0
        client = self._get_client()
        if self._is_site_asset:
            payload = {"targetSoc": soc_decimal}
        else:
            payload = {"chargeSettings": {"targetSoc": soc_decimal}}

        if client and hasattr(client, "_request"):
            client._request("PATCH", self._url(), json=payload, error_label="Failed to set target state of charge")
        elif client and hasattr(client, "get_token"):
            import requests

            token = client.get_token()
            requests.patch(
                self._url(),
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30,
            )

        if self._is_site_asset:
            self._data["targetSoc"] = soc_decimal
        else:
            self._data.setdefault("chargeSettings", {})["targetSoc"] = soc_decimal

    def set_primary_departure_time(self, time_str: str) -> None:
        client = self._get_client()
        if self._is_site_asset:
            payload = {"departureTime": time_str}
        else:
            payload = {"chargeSettings": {"primaryScheduleDepartureTime": time_str}}

        if client and hasattr(client, "_request"):
            client._request("PATCH", self._url(), json=payload, error_label="Failed to set primary departure time")
        elif client and hasattr(client, "get_token"):
            import requests

            token = client.get_token()
            requests.patch(
                self._url(),
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30,
            )

        if self._is_site_asset:
            self._data["departureTime"] = time_str
        else:
            self._data.setdefault("chargeSettings", {})["primaryScheduleDepartureTime"] = time_str

    def __repr__(self) -> str:
        return f"OneKomma5EV(id={self.id()!r}, name={self.name()!r}, mode={self.charging_mode_raw()!r})"
