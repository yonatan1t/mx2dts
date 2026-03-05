"""Serial converter: USART / UART / LPUART → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext

# IOC parameter name → DTS property + value mapping
_PARITY_MAP = {
    "UART_PARITY_NONE": None,
    "UART_PARITY_EVEN": "even",
    "UART_PARITY_ODD":  "odd",
}
_STOP_BITS_MAP = {
    "UART_STOPBITS_0_5": "0_5",
    "UART_STOPBITS_1":   None,    # default — omit
    "UART_STOPBITS_1_5": "1_5",
    "UART_STOPBITS_2":   "2",
}
_DATA_BITS_MAP = {
    "UART_WORDLENGTH_7B": 7,
    "UART_WORDLENGTH_8B": None,   # default — omit
    "UART_WORDLENGTH_9B": 9,
}


class SerialConverter(BaseConverter):
    """Generates DTS nodes for USART, UART, and LPUART instances."""

    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes: list[DtsNode] = []
        for ip in ctx.ioc.active_ips:
            kind = _serial_kind(ip)
            if kind is None:
                continue
            node = self._convert_instance(ip, kind, ctx)
            if node:
                nodes.append(node)
        return nodes

    def _convert_instance(
        self,
        ip_name: str,
        kind: str,
        ctx: ConversionContext,
    ) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        # pinctrl
        pinctrl_labels = []
        for pin in pins:
            lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
            if lbl:
                pinctrl_labels.append(f"&{lbl}")

        if pinctrl_labels:
            props["pinctrl-0"] = f"<{' '.join(pinctrl_labels)}>"
            props["pinctrl-names"] = '"default"'

        # Baud rate
        baud = params.get("BaudRate") or params.get("Init.BaudRate")
        if baud:
            try:
                props["current-speed"] = _cell(int(float(baud)))
            except (ValueError, TypeError):
                ctx.warn(f"{ip_name}: invalid baud rate '{baud}'")

        # Parity
        parity_macro = params.get("Parity") or params.get("Init.Parity", "")
        parity = _PARITY_MAP.get(parity_macro)
        if parity is not None:
            props["parity"] = _quote(parity)

        # Stop bits
        stop_macro = params.get("StopBits") or params.get("Init.StopBits", "")
        stop = _STOP_BITS_MAP.get(stop_macro)
        if stop is not None:
            props["stop-bits"] = _quote(stop)

        # Data bits / word length
        wl_macro = params.get("WordLength") or params.get("Init.WordLength", "")
        data_bits = _DATA_BITS_MAP.get(wl_macro)
        if data_bits is not None:
            props["data-bits"] = _cell(data_bits)

        # Hardware flow control
        hwctl = params.get("HwFlowCtl") or params.get("Init.HwFlowCtl", "")
        if hwctl == "UART_HWCONTROL_RTS_CTS":
            props["hw-flow-control"] = "true"

        props["status"] = '"okay"'

        dts_ref = _ip_to_dts_ref(ip_name)
        return DtsNode(ref=dts_ref, properties=props)


def _serial_kind(ip_name: str) -> str | None:
    if ip_name.startswith("USART"):
        return "usart"
    if ip_name.startswith("UART"):
        return "uart"
    if ip_name.startswith("LPUART"):
        return "lpuart"
    return None


def _ip_to_dts_ref(ip_name: str) -> str:
    """'USART2' → '&usart2'"""
    return f"&{ip_name.lower()}"
