"""I2C converter: I2C instances → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell
from ..context import ConversionContext


_SPEED_MAP = {
    "100000":  "I2C_BITRATE_STANDARD",
    "400000":  "I2C_BITRATE_FAST",
    "1000000": "I2C_BITRATE_FAST_PLUS",
    # CubeMX speed names
    "I2C_SPEED_STANDARD": "I2C_BITRATE_STANDARD",
    "I2C_SPEED_FAST":     "I2C_BITRATE_FAST",
    "I2C_SPEED_FAST_PLUS":"I2C_BITRATE_FAST_PLUS",
}


class I2cConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if not (ip.startswith("I2C") or ip.startswith("FMPI2C")):
                continue
            node = self._convert_instance(ip, ctx)
            if node:
                nodes.append(node)
        return nodes

    def _convert_instance(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        # pinctrl
        pinctrl_labels = []
        for pin in sorted(pins, key=lambda p: p.signal):
            lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
            if lbl:
                pinctrl_labels.append(f"&{lbl}")
        if pinctrl_labels:
            props["pinctrl-0"] = f"<{' '.join(pinctrl_labels)}>"
            props["pinctrl-names"] = '"default"'

        # Clock speed
        speed_raw = (
            params.get("Init.ClockSpeed")
            or params.get("ClockSpeed")
            or params.get("Timing")
        )
        speed = _resolve_speed(speed_raw)
        if speed:
            props["clock-frequency"] = f"<{speed}>"

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props)


def _resolve_speed(raw: str | None) -> str | None:
    if raw is None:
        return None
    # Numeric Hz value
    try:
        hz = int(float(raw))
        return _SPEED_MAP.get(str(hz), str(hz))
    except (ValueError, TypeError):
        pass
    return _SPEED_MAP.get(raw)
