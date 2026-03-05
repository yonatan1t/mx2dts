"""Ethernet / RMII / MII converter → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


# CubeMX MediaInterface → Zephyr phy-connection-type
_PHY_CONN_MAP = {
    "ETH_MEDIA_INTERFACE_RMII": "rmii",
    "ETH_MEDIA_INTERFACE_MII":  "mii",
    "ETH_MEDIA_INTERFACE_RGMII": "rgmii",
}


class EthernetConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if ip not in ("ETH", "ETHERNET"):
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

        # phy-connection-type
        media = params.get("MediaInterface") or params.get("Init.MediaInterface", "")
        conn = _PHY_CONN_MAP.get(media)
        if conn:
            props["phy-connection-type"] = _quote(conn)
        else:
            # Guess from pin count: RMII has fewer pins than MII
            rmii_pins = sum(1 for p in pins if "RMII" in p.signal)
            mii_pins  = sum(1 for p in pins if "_MII_" in p.signal and "RMII" not in p.signal)
            if rmii_pins > 0:
                props["phy-connection-type"] = _quote("rmii")
            elif mii_pins > 0:
                props["phy-connection-type"] = _quote("mii")

        # Look for PHY reset / interrupt GPIOs by label convention
        for pin in ctx.ioc.gpio_pins():
            label_low = (pin.label or "").lower()
            if "phy" in label_low and "rst" in label_low:
                port = f"gpio{pin.name[1].lower()}"
                pin_num = int(pin.name[2:])
                props["phy-reset-gpios"] = f"<&{port} {pin_num} GPIO_ACTIVE_LOW>"
                break

        props["status"] = '"okay"'
        return DtsNode(
            ref="&mac",
            properties=props,
            comment="Verify phy-handle and phy-connection-type for your board",
        )
