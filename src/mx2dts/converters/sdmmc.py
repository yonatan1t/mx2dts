"""SDMMC converter: SDMMC instances → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


class SdmmcConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if not ip.startswith("SDMMC") and not ip.startswith("SDIO"):
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

        # Bus width: count data pins (DAT0..DAT7)
        dat_pins = [p for p in pins if "_DAT" in p.signal or "_D" in p.signal]
        bus_width = max(len(dat_pins), 1)
        # Snap to valid widths: 1, 4, 8
        for valid in (8, 4, 1):
            if bus_width >= valid:
                bus_width = valid
                break
        props["bus-width"] = _cell(bus_width)

        # Clock divider from CLKDIV parameter
        clkdiv = params.get("ClockDiv") or params.get("Init.ClockDiv") or params.get("ClockDivider")
        if clkdiv:
            try:
                props["clk-div"] = _cell(int(clkdiv))
            except (ValueError, TypeError):
                pass

        # Power save mode
        pwr = params.get("ClockPowerSave") or params.get("Init.ClockPowerSave", "")
        if pwr == "SDMMC_CLOCK_POWER_SAVE_ENABLE":
            props["power-delay-ms"] = _cell(1)

        props["status"] = '"okay"'

        # Zephyr node ref: sdmmc1, sdmmc2, sdio → sdio
        ref_name = ip_name.lower().replace("sdio", "sdmmc1")
        return DtsNode(ref=f"&{ref_name}", properties=props)
