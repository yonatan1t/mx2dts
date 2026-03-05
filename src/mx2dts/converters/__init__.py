"""Peripheral converters: IOC → DTS nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..context import ConversionContext


@dataclass
class DtsNode:
    """A single DTS node or overlay fragment."""
    ref: str                             # e.g., "&usart2" or "/ { ... }"
    properties: dict[str, str] = field(default_factory=dict)
    children: list["DtsNode"] = field(default_factory=list)
    comment: Optional[str] = None

    def render(self, indent: int = 0) -> str:
        lines = []
        pad = "\t" * indent
        if self.comment:
            lines.append(f"{pad}/* {self.comment} */")
        lines.append(f"{pad}{self.ref} {{")
        for k, v in self.properties.items():
            lines.append(f"{pad}\t{k} = {v};")
        for child in self.children:
            lines.append(child.render(indent + 1))
        lines.append(f"{pad}}};")
        return "\n".join(lines)


class BaseConverter:
    """Base class for all peripheral converters."""

    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        raise NotImplementedError

    def name(self) -> str:
        return self.__class__.__name__


def _quote(s: str) -> str:
    return f'"{s}"'


def _cell(v) -> str:
    return f"<{v}>"


def _freq_macro(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"<DT_FREQ_M({hz // 1_000_000})>"
    if hz % 1_000 == 0:
        return f"<DT_FREQ_K({hz // 1_000})>"
    return f"<{hz}>"


# Re-export all converters
from .clocks import ClocksConverter
from .gpio import GpioConverter
from .serial import SerialConverter
from .spi import SpiConverter
from .i2c import I2cConverter
from .adc import AdcConverter
from .dma import DmaConverter
from .timers import TimersConverter

ALL_CONVERTERS: list[type[BaseConverter]] = [
    ClocksConverter,
    DmaConverter,       # DMA before peripherals (so dmas= props can be set)
    GpioConverter,
    SerialConverter,
    SpiConverter,
    I2cConverter,
    AdcConverter,
    TimersConverter,
]
