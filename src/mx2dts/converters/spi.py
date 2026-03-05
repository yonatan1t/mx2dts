"""SPI converter: SPI instances → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


class SpiConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if not ip.startswith("SPI"):
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

        # Clock prescaler → clock-frequency approx
        prescaler = params.get("Init.CLKPhase") or params.get("BaudRatePrescaler")
        # CS GPIO — look for NSS pin if it's in GPIO mode
        nss_gpio = _find_nss_gpio(ip_name, ctx)
        if nss_gpio:
            port, pin_num = nss_gpio
            props["cs-gpios"] = f"<&{port} {pin_num} (GPIO_ACTIVE_LOW | GPIO_PULL_UP)>"

        # Clock polarity / phase
        cpol = params.get("Init.CLKPolarity", "")
        cpha = params.get("Init.CLKPhase", "")
        mode = _cpol_cpha_to_mode(cpol, cpha)
        if mode is not None:
            # Zephyr uses spi-cpol / spi-cpha on child nodes but not on the controller
            # Just add a comment for the user
            pass

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props)


def _find_nss_gpio(ip_name: str, ctx: ConversionContext):
    """Find NSS/CS pin if it's configured as GPIO (software CS)."""
    nss_signal = f"{ip_name}_NSS"
    for pin in ctx.ioc.pins.values():
        if pin.signal == nss_signal and pin.is_gpio:
            port_letter = pin.name[1].lower()
            pin_num = int(pin.name[2:])
            return f"gpio{port_letter}", pin_num
    return None


def _cpol_cpha_to_mode(cpol: str, cpha: str) -> int | None:
    mapping = {
        ("SPI_POLARITY_LOW",  "SPI_PHASE_1EDGE"): 0,
        ("SPI_POLARITY_LOW",  "SPI_PHASE_2EDGE"): 1,
        ("SPI_POLARITY_HIGH", "SPI_PHASE_1EDGE"): 2,
        ("SPI_POLARITY_HIGH", "SPI_PHASE_2EDGE"): 3,
    }
    return mapping.get((cpol, cpha))
