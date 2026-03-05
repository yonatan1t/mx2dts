"""Timer converter: TIM instances → Zephyr &timersN / PWM nodes."""

from __future__ import annotations

import re
from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


class TimersConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if not re.match(r"^TIM\d+$", ip):
                continue
            node = self._convert_timer(ip, ctx)
            if node:
                nodes.append(node)
        return nodes

    def _convert_timer(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        # Separate PWM-capable channels from encoder/input pins
        pwm_pins = [p for p in pins if "_CH" in p.signal and "N" not in p.signal.split("_CH")[-1]]
        other_pins = [p for p in pins if p not in pwm_pins]

        dts_name = f"timers{ip_name[3:]}"  # TIM2 → timers2
        props: dict[str, str] = {}

        prescaler = params.get("Init.Prescaler") or params.get("Prescaler")
        if prescaler:
            try:
                props["st,prescaler"] = _cell(int(prescaler))
            except (ValueError, TypeError):
                pass

        props["status"] = '"okay"'

        children = []
        if pwm_pins:
            pwm_node = self._make_pwm_node(ip_name, pwm_pins, ctx)
            if pwm_node:
                children.append(pwm_node)

        return DtsNode(ref=f"&{dts_name}", properties=props, children=children)

    def _make_pwm_node(
        self,
        ip_name: str,
        pwm_pins: list,
        ctx: ConversionContext,
    ) -> DtsNode | None:
        pinctrl_labels = []
        for pin in sorted(pwm_pins, key=lambda p: p.signal):
            lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
            if lbl:
                pinctrl_labels.append(f"&{lbl}")

        props: dict[str, str] = {"status": '"okay"'}
        if pinctrl_labels:
            props["pinctrl-0"] = f"<{' '.join(pinctrl_labels)}>"
            props["pinctrl-names"] = '"default"'

        pwm_name = f"pwm{ip_name[3:]}"  # TIM2 → pwm2
        return DtsNode(
            ref=f"{pwm_name}: pwm",
            properties=props,
        )
