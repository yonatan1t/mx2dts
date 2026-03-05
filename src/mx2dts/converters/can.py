"""CAN / FDCAN converter: CAN and FDCAN instances → Zephyr DTS nodes."""

from __future__ import annotations

from typing import Optional

from . import BaseConverter, DtsNode, _cell, _quote
from ..context import ConversionContext


class CanConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        for ip in ctx.ioc.active_ips:
            if ip.startswith("FDCAN"):
                node = self._convert_fdcan(ip, ctx)
            elif ip.startswith("CAN"):
                node = self._convert_can(ip, ctx)
            else:
                continue
            if node:
                nodes.append(node)
        return nodes

    def _convert_can(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        _add_pinctrl(props, pins, ctx)

        prescaler = _int_param(params, "InitBitTimePrescaler", "Init.Prescaler")
        ts1 = _int_param(params, "InitTimeSeg1", "Init.TimeSeg1")
        ts2 = _int_param(params, "InitTimeSeg2", "Init.TimeSeg2")

        apb1_hz = _apb1_hz(ctx)

        if prescaler is not None and ts1 is not None and ts2 is not None:
            if apb1_hz is not None:
                bus_speed = apb1_hz // (prescaler * (1 + ts1 + ts2))
                props["bus-speed"] = _cell(bus_speed)
            else:
                ctx.warn(
                    f"{ip_name}: APB1 clock frequency unknown; "
                    "set bus-speed manually in the generated overlay"
                )
                props["/* TODO: bus-speed"] = "*/ <500000>"

            sample_point = (1 + ts1) * 1000 // (1 + ts1 + ts2)
            props["sample-point"] = _cell(sample_point)

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props)

    def _convert_fdcan(self, ip_name: str, ctx: ConversionContext) -> DtsNode | None:
        params = ctx.ioc.get_ip_params(ip_name)
        pins = ctx.ioc.pins_for_peripheral(ip_name)

        props: dict[str, str] = {}

        _add_pinctrl(props, pins, ctx)

        # Nominal bit timing
        nom_prescaler = _int_param(params, "InitNominalBitRatePrescaler")
        nom_ts1 = _int_param(params, "InitNominalTimeSeg1")
        nom_ts2 = _int_param(params, "InitNominalTimeSeg2")

        # Data phase bit timing
        data_prescaler = _int_param(params, "InitDataBitRatePrescaler")
        data_ts1 = _int_param(params, "InitDataTimeSeg1")
        data_ts2 = _int_param(params, "InitDataTimeSeg2")

        apb1_hz = _apb1_hz(ctx)

        if nom_prescaler is not None and nom_ts1 is not None and nom_ts2 is not None:
            if apb1_hz is not None:
                bus_speed = apb1_hz // (nom_prescaler * (1 + nom_ts1 + nom_ts2))
                props["bus-speed"] = _cell(bus_speed)
            else:
                ctx.warn(
                    f"{ip_name}: APB1 clock frequency unknown; "
                    "set bus-speed manually in the generated overlay"
                )
                props["/* TODO: bus-speed"] = "*/ <500000>"

            sample_point = (1 + nom_ts1) * 1000 // (1 + nom_ts1 + nom_ts2)
            props["sample-point"] = _cell(sample_point)

        if data_prescaler is not None and data_ts1 is not None and data_ts2 is not None:
            if apb1_hz is not None:
                bus_speed_data = apb1_hz // (data_prescaler * (1 + data_ts1 + data_ts2))
                props["bus-speed-data"] = _cell(bus_speed_data)
            else:
                props["/* TODO: bus-speed-data"] = "*/ <2000000>"

            sample_point_data = (1 + data_ts1) * 1000 // (1 + data_ts1 + data_ts2)
            props["sample-point-data"] = _cell(sample_point_data)

        props["status"] = '"okay"'
        return DtsNode(ref=f"&{ip_name.lower()}", properties=props)


# ── Utilities ──────────────────────────────────────────────────────────────────

def _add_pinctrl(
    props: dict[str, str],
    pins: list,
    ctx: ConversionContext,
) -> None:
    labels = []
    for pin in sorted(pins, key=lambda p: p.signal):
        lbl = ctx.resolve_pinctrl_label(pin.signal, pin.name)
        if lbl:
            labels.append(f"&{lbl}")
    if labels:
        props["pinctrl-0"] = f"<{' '.join(labels)}>"
        props["pinctrl-names"] = '"default"'


def _int_param(params: dict[str, str], *keys: str) -> Optional[int]:
    """Return the integer value of the first matching key, or None."""
    for key in keys:
        raw = params.get(key)
        if raw is not None:
            try:
                return int(float(raw))
            except (ValueError, TypeError):
                pass
    return None


def _apb1_hz(ctx: ConversionContext) -> Optional[int]:
    raw = ctx.ioc.get_rcc().get("APB1Freq_Value")
    try:
        return int(float(raw)) if raw else None
    except (ValueError, TypeError):
        return None
