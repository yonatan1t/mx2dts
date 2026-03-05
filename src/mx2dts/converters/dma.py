"""DMA converter: IOC DMA config → Zephyr dmas= properties on peripheral nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import BaseConverter, DtsNode
from ..context import ConversionContext
from ..dma_db import get_dma_request, is_dmamux_family


@dataclass
class DmaAssignment:
    peripheral: str      # e.g., "USART2"
    signal: str          # e.g., "USART2_RX"
    direction: str       # "rx" or "tx"
    controller: str      # e.g., "dma1"
    channel: int         # channel number (1-indexed as in CubeMX)
    request: Optional[int]   # DMA request / DMAMUX slot (None if unknown)
    priority: int        # 0=low … 3=very high
    config_flags: str    # hex string for Zephyr DMA config cell, e.g., "0x440"
    circular: bool = False


_PRIORITY_MAP = {
    "DMA_PRIORITY_LOW":       0,
    "DMA_PRIORITY_MEDIUM":    1,
    "DMA_PRIORITY_HIGH":      2,
    "DMA_PRIORITY_VERY_HIGH": 3,
}

_DIRECTION_MAP = {
    "DMA_PERIPH_TO_MEMORY": "rx",
    "DMA_MEMORY_TO_PERIPH": "tx",
    "DMA_MEMORY_TO_MEMORY": "mem2mem",
}

# ── DMA config-cell flag bits (Zephyr STM32 DMA binding) ──────────────────────
# See include/zephyr/dt-bindings/dma/stm32_dma.h
#   bits [7:6] periph data width: 0=8b, 1=16b, 2=32b
#   bits [5:4] memory data width: 0=8b, 1=16b, 2=32b
#   bit  [3]   periph-no-inc (1=no-inc, 0=inc)
#   bit  [2]   mem-no-inc    (1=no-inc, 0=inc)
#   bit  [1:0] unused (flow control)

_PERIPH_WIDTH = {
    "DMA_PDATAALIGN_BYTE":     0b00 << 6,
    "DMA_PDATAALIGN_HALFWORD": 0b01 << 6,
    "DMA_PDATAALIGN_WORD":     0b10 << 6,
}
_MEM_WIDTH = {
    "DMA_MDATAALIGN_BYTE":     0b00 << 4,
    "DMA_MDATAALIGN_HALFWORD": 0b01 << 4,
    "DMA_MDATAALIGN_WORD":     0b10 << 4,
}
_PERIPH_NO_INC = 0b1 << 3   # DMA_PINC_DISABLE
_MEM_NO_INC    = 0b1 << 2   # DMA_MINC_DISABLE


def _compute_config_flags(entry: dict[str, str]) -> str:
    """Compute the Zephyr DMA config cell value from IOC DMA parameters."""
    flags = 0
    flags |= _PERIPH_WIDTH.get(entry.get("PeriphDataAlignment", ""), 0)
    flags |= _MEM_WIDTH.get(entry.get("MemDataAlignment", ""), 0)
    if entry.get("PeriphInc", "") == "DMA_PINC_DISABLE":
        flags |= _PERIPH_NO_INC
    if entry.get("MemInc", "") == "DMA_MINC_DISABLE":
        flags |= _MEM_NO_INC
    return f"0x{flags:x}" if flags else "0x0"


class DmaConverter(BaseConverter):
    """Collects DMA assignments and attaches them to peripheral DTS nodes."""

    def __init__(self):
        # Map peripheral_lower → {prop_name: value} ready to inject
        self.peripheral_dma_props: dict[str, dict[str, str]] = {}

    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        dma_config = ctx.ioc.get_dma_config()
        if not dma_config:
            return []

        assignments: list[DmaAssignment] = []
        for signal, entries in dma_config.items():
            for entry in entries:
                asn = self._parse_assignment(signal, entry, ctx)
                if asn:
                    assignments.append(asn)

        # Group by peripheral
        by_peripheral: dict[str, list[DmaAssignment]] = {}
        for asn in assignments:
            by_peripheral.setdefault(asn.peripheral, []).append(asn)

        for peripheral, asns in by_peripheral.items():
            # Sort: rx before tx, then by channel
            asns.sort(key=lambda a: (a.direction, a.channel))
            dmas_cells = []
            dma_names = []
            has_unknown_request = False

            for asn in asns:
                req = asn.request if asn.request is not None else 0
                if asn.request is None:
                    has_unknown_request = True
                dmas_cells.append(
                    f"<&{asn.controller} {asn.channel} {req} {asn.config_flags} {asn.priority}>"
                )
                dma_names.append(f'"{asn.direction}"')

            self.peripheral_dma_props[peripheral.lower()] = {
                "dmas": " ".join(dmas_cells),
                "dma-names": ", ".join(dma_names),
            }
            if has_unknown_request:
                ctx.warn(
                    f"{peripheral}: DMA request number(s) could not be determined. "
                    "Verify the 'dmas' cell against your MCU's DMA request table."
                )

        # DMA controller nodes (just enable them)
        controllers = sorted({a.controller for a in assignments})
        nodes = [DtsNode(ref=f"&{c}", properties={"status": '"okay"'}) for c in controllers]
        return nodes

    def _parse_assignment(
        self,
        signal: str,
        entry: dict[str, str],
        ctx: ConversionContext,
    ) -> Optional[DmaAssignment]:
        channel_str = entry.get("Channel", "")
        # e.g., "DMA1_Channel6"
        m = re.match(r"(DMA\d+)_Channel(\d+)", channel_str, re.IGNORECASE)
        if not m:
            ctx.warn(f"DMA: cannot parse channel '{channel_str}' for signal '{signal}'")
            return None

        controller = m.group(1).lower()      # "dma1"
        channel_num = int(m.group(2))        # 6  (1-indexed)

        # Zephyr STM32 DMA uses 0-indexed channels for DMAMUX families
        zephyr_channel = (channel_num - 1) if is_dmamux_family(ctx.mcu.family) else channel_num

        direction_macro = entry.get("Direction", "")
        direction = _DIRECTION_MAP.get(direction_macro, "")
        if not direction:
            ctx.warn(f"DMA: unknown direction '{direction_macro}' for signal '{signal}'")
            direction = "rx"

        priority = _PRIORITY_MAP.get(entry.get("Priority", "DMA_PRIORITY_LOW"), 0)
        circular = entry.get("Mode", "") == "DMA_CIRCULAR"
        config_flags = _compute_config_flags(entry)

        # Look up DMA request number
        request = get_dma_request(
            signal,
            channel_str,
            ctx.mcu,
            ctx.cubemx,
        )

        peripheral = signal.rsplit("_", 1)[0] if "_" in signal else signal

        return DmaAssignment(
            peripheral=peripheral,
            signal=signal,
            direction=direction,
            controller=controller,
            channel=zephyr_channel,
            request=request,
            priority=priority,
            config_flags=config_flags,
            circular=circular,
        )
