"""DMA converter: IOC DMA config → Zephyr dmas= properties on peripheral nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import BaseConverter, DtsNode
from ..context import ConversionContext


@dataclass
class DmaAssignment:
    peripheral: str      # e.g., "USART2"
    direction: str       # "rx" or "tx"
    controller: str      # e.g., "dma1"
    channel: int         # channel number
    request: int         # DMA request number (DMAMUX slot)
    priority: int        # 0=low, 1=medium, 2=high, 3=very high
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


class DmaConverter(BaseConverter):
    """Collects DMA assignments and attaches them to peripheral DTS nodes."""

    def __init__(self):
        # Map peripheral → list[DtsNode properties to inject]
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

        # Group by peripheral and build dmas= + dma-names= properties
        by_peripheral: dict[str, list[DmaAssignment]] = {}
        for asn in assignments:
            by_peripheral.setdefault(asn.peripheral, []).append(asn)

        nodes: list[DtsNode] = []
        for peripheral, asns in by_peripheral.items():
            asns.sort(key=lambda a: a.direction)
            dmas_cells = []
            dma_names = []
            for asn in asns:
                # Zephyr STM32 DMA cell: <&dmaX channel request slot flags>
                # For pre-DMAMUX: <&dmaX channel request 0x0 0x3>
                # For DMAMUX: <&dmaX channel slot 0x0 flags>
                dmas_cells.append(
                    f"<&{asn.controller} {asn.channel} {asn.request} 0x0 {asn.priority}>"
                )
                dma_names.append(f'"{asn.direction}"')

            props = {
                "dmas": " ".join(dmas_cells),
                "dma-names": ", ".join(dma_names),
            }
            # Store for merging into peripheral node (not standalone node)
            self.peripheral_dma_props[peripheral.lower()] = props

        if self.peripheral_dma_props:
            ctx.warn(
                "DMA assignments were extracted. They need to be merged into the "
                "respective peripheral nodes. Check the DMA cell values against "
                "the Zephyr binding for your MCU."
            )

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

        controller = m.group(1).lower()  # "dma1"
        channel_num = int(m.group(2))

        direction_macro = entry.get("Direction", "")
        direction = _DIRECTION_MAP.get(direction_macro, "")
        if not direction:
            ctx.warn(f"DMA: unknown direction '{direction_macro}' for signal '{signal}'")
            direction = "rx"

        priority_macro = entry.get("Priority", "DMA_PRIORITY_LOW")
        priority = _PRIORITY_MAP.get(priority_macro, 0)

        mode = entry.get("Mode", "")
        circular = mode == "DMA_CIRCULAR"

        # Derive peripheral from signal (e.g., "USART2_RX" → "USART2")
        peripheral = signal.rsplit("_", 1)[0] if "_" in signal else signal

        # Request number: This is MCU-specific and requires the DMA request mapping
        # from the CubeMX DB. For now, we use 0 as a placeholder and warn the user.
        request = 0
        ctx.warn(
            f"DMA request number for {signal} is MCU-specific. "
            f"Please verify '{controller} channel {channel_num}' DMA request in the "
            "Zephyr DMA binding documentation."
        )

        return DmaAssignment(
            peripheral=peripheral,
            direction=direction,
            controller=controller,
            channel=channel_num,
            request=request,
            priority=priority,
            circular=circular,
        )
