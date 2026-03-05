"""GPIO converter: plain GPIO pins → gpio-leds / gpio-keys / gpio-hog nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext
from ..ioc_parser import PinConfig


# GPIO_Mode values that suggest output direction
_OUTPUT_MODES = {"GPIO_MODE_OUTPUT_PP", "GPIO_MODE_OUTPUT_OD", "GPIO_OUTPUT", "GPIO_Output"}
_INPUT_MODES  = {"GPIO_MODE_INPUT", "GPIO_INPUT", "GPIO_Input"}


class GpioConverter(BaseConverter):
    """Generates gpio-leds and gpio-keys nodes from plain GPIO pin configs."""

    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        gpio_pins = [p for p in ctx.ioc.pins.values() if p.is_gpio]
        if not gpio_pins:
            return []

        outputs = [p for p in gpio_pins if _is_output(p)]
        inputs  = [p for p in gpio_pins if _is_input(p)]

        nodes: list[DtsNode] = []

        if outputs:
            leds_node = _make_gpio_leds(outputs)
            if leds_node:
                nodes.append(leds_node)

        if inputs:
            keys_node = _make_gpio_keys(inputs)
            if keys_node:
                nodes.append(keys_node)

        # Any remaining GPIO pins that aren't clearly leds/keys: emit as comments
        others = [p for p in gpio_pins if not _is_output(p) and not _is_input(p)]
        for pin in others:
            ctx.warn(
                f"GPIO pin {pin.name} ({pin.label or pin.signal}) has unknown "
                f"direction (GPIO_Mode='{pin.gpio_mode}') — skipped"
            )

        return nodes


def _gpio_port_pin(pin_name: str) -> tuple[str, int]:
    """'PA5' → ('gpioa', 5)"""
    port_letter = pin_name[1].lower()
    pin_num = int(pin_name[2:])
    return f"gpio{port_letter}", pin_num


def _active_flag(pin: PinConfig) -> str:
    pull = (pin.pull or "").upper()
    if "PULLUP" in pull or pull == "GPIO_PULLUP":
        return "GPIO_ACTIVE_LOW"
    return "GPIO_ACTIVE_HIGH"


def _make_gpio_leds(outputs: list[PinConfig]) -> DtsNode:
    node = DtsNode(
        ref="leds",
        properties={"compatible": '"gpio-leds"'},
    )
    for pin in outputs:
        port, pin_num = _gpio_port_pin(pin.name)
        label = pin.label or pin.name.lower()
        node_name = label.lower().replace(" ", "_").replace("-", "_")
        flag = _active_flag(pin)
        child = DtsNode(
            ref=f"{node_name}: {node_name}",
            properties={
                "gpios": f"<&{port} {pin_num} {flag}>",
                "label": _quote(label),
            },
        )
        node.children.append(child)
    return node


def _make_gpio_keys(inputs: list[PinConfig]) -> DtsNode:
    node = DtsNode(
        ref="gpio_keys",
        properties={"compatible": '"gpio-keys"'},
    )
    for i, pin in enumerate(inputs):
        port, pin_num = _gpio_port_pin(pin.name)
        label = pin.label or pin.name.lower()
        node_name = label.lower().replace(" ", "_").replace("-", "_")
        flag = _active_flag(pin)
        child = DtsNode(
            ref=f"{node_name}: {node_name}",
            properties={
                "label": _quote(label),
                "gpios": f"<&{port} {pin_num} {flag}>",
                "zephyr,code": f"<INPUT_KEY_{i}>",
            },
        )
        node.children.append(child)
    return node


def _is_output(pin: PinConfig) -> bool:
    if pin.gpio_mode in _OUTPUT_MODES:
        return True
    if pin.signal in ("GPIO_Output",):
        return True
    return False


def _is_input(pin: PinConfig) -> bool:
    if pin.gpio_mode in _INPUT_MODES:
        return True
    if pin.signal in ("GPIO_Input",):
        return True
    return False
