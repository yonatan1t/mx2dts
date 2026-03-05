"""SAI (Serial Audio Interface) converter → Zephyr DTS nodes."""

from __future__ import annotations

import re
from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


# CubeMX audio protocol → Zephyr compatible
_PROTOCOL_MAP = {
    "SAI_I2S_STANDARD":    "i2s",
    "SAI_I2S_MSBJUSTIFIED":"i2s",
    "SAI_I2S_LSBJUSTIFIED":"i2s",
    "SAI_PCM_LONG":        "pcm",
    "SAI_PCM_SHORT":       "pcm",
    "SAI_AC97_PROTOCOL":   "ac97",
}


class SaiConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if not re.match(r"^SAI\d+$", ip):
                continue
            node = self._convert_instance(ip, ctx)
            if node:
                nodes.append(node)
        return nodes

    def _convert_instance(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        pinctrl_labels = []
        for pin in sorted(pins, key=lambda p: p.signal):
            lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
            if lbl:
                pinctrl_labels.append(f"&{lbl}")
        if pinctrl_labels:
            props["pinctrl-0"] = f"<{' '.join(pinctrl_labels)}>"
            props["pinctrl-names"] = '"default"'

        # Audio protocol / frame format
        protocol = params.get("Protocol") or params.get("Init.Protocol", "")
        fmt = _PROTOCOL_MAP.get(protocol)
        if fmt:
            props["format"] = _quote(fmt)

        # MCLK division (SAI2 / SAI4 on H7 etc.)
        mclk_div = params.get("MckDiv") or params.get("Init.MckDiv") or params.get("MckOverSampling")
        if mclk_div:
            try:
                props["mclk-fs"] = _cell(int(mclk_div))
            except (ValueError, TypeError):
                pass

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props)
