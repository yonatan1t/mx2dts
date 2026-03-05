"""RNG and CRC converters → Zephyr DTS nodes (status = "okay" only)."""

from __future__ import annotations

from . import BaseConverter, DtsNode
from ..context import ConversionContext

_OKAY = {"status": '"okay"'}


class RngConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        if ctx.ioc.has_ip("RNG"):
            return [DtsNode(ref="&rng", properties=dict(_OKAY))]
        return []


class CrcConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        if ctx.ioc.has_ip("CRC"):
            return [DtsNode(ref="&crc", properties=dict(_OKAY))]
        return []
