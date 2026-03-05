"""I2S converter → Zephyr DTS nodes."""

from __future__ import annotations

import re
from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


# CubeMX standard → Zephyr format
_FORMAT_MAP = {
    "I2S_STANDARD_PHILIPS":        "i2s_philips",
    "I2S_STANDARD_MSB":            "left_justified",
    "I2S_STANDARD_LSB":            "right_justified",
    "I2S_STANDARD_PCM_SHORT":      "pcm_short",
    "I2S_STANDARD_PCM_LONG":       "pcm_long",
}

# CubeMX data format → word size in bits
_DATAFORMAT_MAP = {
    "I2S_DATAFORMAT_16B":          16,
    "I2S_DATAFORMAT_16B_EXTENDED": 16,
    "I2S_DATAFORMAT_24B":          24,
    "I2S_DATAFORMAT_32B":          32,
}


class I2sConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            # I2S can be a standalone IP or a sub-mode of SPI
            if not re.match(r"^I2S\d+$", ip) and not re.match(r"^SPI\d+$", ip):
                continue
            if re.match(r"^SPI\d+$", ip):
                # Only process SPI as I2S if it is configured in I2S mode
                params = ctx.ioc.get_ip_params(ip)
                if not any("I2S" in v for v in params.values()):
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

        std = params.get("Standard") or params.get("Init.Standard", "")
        fmt = _FORMAT_MAP.get(std)
        if fmt:
            props["format"] = _quote(fmt)

        data_fmt = params.get("DataFormat") or params.get("Init.DataFormat", "")
        word_size = _DATAFORMAT_MAP.get(data_fmt)
        if word_size:
            props["word-size"] = _cell(word_size)

        props["status"] = '"okay"'
        # I2S2/3 on SPI2/3 nodes are &i2s2 / &i2s3 in Zephyr
        ref_name = ip_name.lower().replace("spi", "i2s")
        return DtsNode(ref=f"&{ref_name}", properties=props)
