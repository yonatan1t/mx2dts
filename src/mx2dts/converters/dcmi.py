"""DCMI (Digital Camera Interface) converter → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


class DcmiConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        if not ctx.ioc.has_ip("DCMI"):
            return []
        return [self._convert_instance(ctx)]

    def _convert_instance(self, ctx: ConversionContext) -> DtsNode:
        params = ctx.ioc.get_ip_params("DCMI")
        pins = ctx.ioc.pins_for_peripheral("DCMI")

        props: dict[str, str] = {}

        pinctrl_labels = []
        for pin in sorted(pins, key=lambda p: p.signal):
            lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
            if lbl:
                pinctrl_labels.append(f"&{lbl}")
        if pinctrl_labels:
            props["pinctrl-0"] = f"<{' '.join(pinctrl_labels)}>"
            props["pinctrl-names"] = '"default"'

        # Capture mode
        capture_rate = params.get("CaptureRate") or params.get("Init.CaptureRate", "")
        if capture_rate == "DCMI_CR_ALL_FRAME":
            props["bus-width"] = _cell(8)
        elif "DCMI_EXTENDED_DATA_14" in capture_rate:
            props["bus-width"] = _cell(14)
        elif "DCMI_EXTENDED_DATA_12" in capture_rate:
            props["bus-width"] = _cell(12)
        elif "DCMI_EXTENDED_DATA_10" in capture_rate:
            props["bus-width"] = _cell(10)

        # Sync mode
        sync = params.get("SynchroMode") or params.get("Init.SynchroMode", "")
        if sync == "DCMI_SYNCHRO_EMBEDDED":
            props["hsync-active"] = _cell(0)
            props["vsync-active"] = _cell(0)
        else:
            # External sync — read polarity params
            hsync = params.get("HSPolarity") or params.get("Init.HSPolarity", "")
            vsync = params.get("VSPolarity") or params.get("Init.VSPolarity", "")
            props["hsync-active"] = _cell(0 if hsync == "DCMI_HSPOLARITY_LOW" else 1)
            props["vsync-active"] = _cell(0 if vsync == "DCMI_VSPOLARITY_LOW" else 1)

        pclk = params.get("PCKPolarity") or params.get("Init.PCKPolarity", "")
        props["pclk-sample"] = _cell(1 if pclk == "DCMI_PCKPOLARITY_RISING" else 0)

        props["status"] = '"okay"'
        return DtsNode(ref="&dcmi", properties=props)
