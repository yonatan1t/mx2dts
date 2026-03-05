"""ADC / DAC converter → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


_ADC_CLOCK_SOURCE_MAP = {
    "ADC_CLOCK_SYNC_PCLK_DIV1": "SYNC",
    "ADC_CLOCK_SYNC_PCLK_DIV2": "SYNC",
    "ADC_CLOCK_SYNC_PCLK_DIV4": "SYNC",
    "ADC_CLOCK_ASYNC_DIV1":     "ASYNC",
}

_ADC_PRESCALER_MAP = {
    "ADC_CLOCK_SYNC_PCLK_DIV1": 1,
    "ADC_CLOCK_SYNC_PCLK_DIV2": 2,
    "ADC_CLOCK_SYNC_PCLK_DIV4": 4,
}


class AdcConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if ip.startswith("ADC"):
                node = self._convert_adc(ip, ctx)
            elif ip.startswith("DAC"):
                node = self._convert_dac(ip, ctx)
            else:
                continue
            if node:
                nodes.append(node)
        return nodes

    def _convert_adc(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        # ADC input pins (ANALOG mode)
        pinctrl_labels = []
        for pin in sorted(pins, key=lambda p: p.signal):
            lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
            if lbl:
                pinctrl_labels.append(f"&{lbl}")
        if pinctrl_labels:
            props["pinctrl-0"] = f"<{' '.join(pinctrl_labels)}>"
            props["pinctrl-names"] = '"default"'

        # Clock source
        clk_src_macro = params.get("ClockPrescaler") or params.get("Init.ClockPrescaler", "")
        clk_src = _ADC_CLOCK_SOURCE_MAP.get(clk_src_macro)
        if clk_src:
            props["st,adc-clock-source"] = _quote(clk_src)
        prescaler = _ADC_PRESCALER_MAP.get(clk_src_macro)
        if prescaler:
            props["st,adc-prescaler"] = _cell(prescaler)

        # VREF / VBAT internal channels — emit as child nodes if configured
        children = self._internal_channels(ip_name, params, ctx)

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props, children=children)

    def _convert_dac(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
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

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props)

    def _internal_channels(
        self,
        ip_name: str,
        params: dict[str, str],
        ctx: ConversionContext,
    ) -> list[DtsNode]:
        """Emit &vref / &vbat nodes if the ADC has those channels enabled."""
        nodes = []
        # Detect if VREF or VBAT internal channels are configured
        # (CubeMX usually puts them as separate IPs: VREF, VBAT)
        for virt_ip in ("VREF", "VBAT", "VREFBUF"):
            if ctx.ioc.has_ip(virt_ip):
                nodes.append(DtsNode(
                    ref=f"&{virt_ip.lower()}",
                    properties={"status": '"okay"'},
                ))
        return nodes
