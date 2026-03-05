"""USB OTG FS / HS / device-FS converter → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _quote
from ..context import ConversionContext


# Maps ip_name → Zephyr DTS node reference
_IP_TO_REF: dict[str, str] = {
    "USB_OTG_FS": "usbotg_fs",
    "USB_OTG_HS": "usbotg_hs",
    "USB":        "usb",
}

# CubeMX speed parameter values that indicate full-speed
_FS_SPEED_VALUES = frozenset({
    "USB_OTG_FS_SPEED",
    "USB_SPEED_FULL",
    "FULL_SPEED",
})

# PHY type values that indicate the internal HS PHY (no external ULPI pins)
_INTERNAL_HS_PHY_VALUES = frozenset({
    "USB_OTG_HS_INTERNAL_HS_PHY",
    "USB_OTG_HS_EMBEDDED_PHY",
})


class UsbConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if ip not in _IP_TO_REF:
                continue
            node = self._convert_instance(ip, ctx)
            if node:
                nodes.append(node)
        return nodes

    def _convert_instance(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        # OTG HS with internal PHY has no external ULPI pins — skip pinctrl.
        # For FS and external-PHY HS, emit pinctrl if pins are assigned.
        phy_type = params.get("PHYType", "")
        has_internal_phy = phy_type in _INTERNAL_HS_PHY_VALUES

        if not has_internal_phy:
            labels = []
            for pin in sorted(pins, key=lambda p: p.signal):
                lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
                if lbl:
                    labels.append(f"&{lbl}")
            if labels:
                props["pinctrl-0"] = f"<{' '.join(labels)}>"
                props["pinctrl-names"] = '"default"'

        # maximum-speed
        speed_raw = params.get("Init.Speed") or params.get("Speed", "")
        speed = _resolve_speed(ip_name, speed_raw)
        if speed:
            props["maximum-speed"] = _quote(speed)

        props["status"] = '"okay"'

        dts_ref = _IP_TO_REF[ip_name]
        return DtsNode(ref=f"&{dts_ref}", properties=props)


def _resolve_speed(ip_name: str, speed_raw: str) -> str | None:
    """Map a CubeMX speed value to a Zephyr maximum-speed string."""
    if not speed_raw:
        # Infer from the IP name when no explicit speed parameter is present
        if "FS" in ip_name:
            return "full-speed"
        if "HS" in ip_name:
            return "high-speed"
        return None

    if speed_raw in _FS_SPEED_VALUES or "FS" in speed_raw.upper():
        return "full-speed"
    if "HS" in speed_raw.upper() or "HIGH" in speed_raw.upper():
        return "high-speed"
    return None
