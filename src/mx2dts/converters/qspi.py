"""QUADSPI / OCTOSPI converter → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


class QspiConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if ip in ("QUADSPI", "QSPI"):
                node = self._convert_qspi(ip, ctx)
            elif ip.startswith("OCTOSPI") or ip.startswith("OSPI"):
                node = self._convert_octospi(ip, ctx)
            else:
                continue
            if node:
                nodes.append(node)
        return nodes

    def _convert_qspi(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)
        props: dict[str, str] = {}

        _add_pinctrl(pins, props, ctx)

        prescaler = params.get("ClockPrescaler") or params.get("Init.ClockPrescaler")
        if prescaler:
            try:
                props["clock-prescaler"] = _cell(int(prescaler))
            except (ValueError, TypeError):
                pass

        flash_size = params.get("FlashSize") or params.get("Init.FlashSize")
        if flash_size:
            try:
                # CubeMX stores flash size as exponent (2^(n+1) bytes)
                props["flash-size"] = _cell(int(flash_size))
            except (ValueError, TypeError):
                pass

        props["status"] = '"okay"'
        return DtsNode(ref="&quadspi", properties=props)

    def _convert_octospi(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)
        props: dict[str, str] = {}

        _add_pinctrl(pins, props, ctx)

        prescaler = params.get("ClockPrescaler") or params.get("Init.ClockPrescaler")
        if prescaler:
            try:
                props["clock-prescaler"] = _cell(int(prescaler))
            except (ValueError, TypeError):
                pass

        props["status"] = '"okay"'
        # e.g. OCTOSPI1 → &octospi1
        ref = ip_name.lower().replace("ospi", "octospi")
        return DtsNode(ref=f"&{ref}", properties=props)


def _add_pinctrl(pins, props: dict, ctx: ConversionContext) -> None:
    labels = []
    for pin in sorted(pins, key=lambda p: p.signal):
        lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
        if lbl:
            labels.append(f"&{lbl}")
    if labels:
        props["pinctrl-0"] = f"<{' '.join(labels)}>"
        props["pinctrl-names"] = '"default"'
