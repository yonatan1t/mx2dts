"""Watchdog converter: IWDG + WWDG instances → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode
from ..context import ConversionContext

_OKAY: dict[str, str] = {"status": '"okay"'}


class WatchdogConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        if ctx.ioc.has_ip("IWDG"):
            nodes.append(DtsNode(ref="&iwdg", properties=dict(_OKAY)))
        if ctx.ioc.has_ip("WWDG"):
            nodes.append(DtsNode(ref="&wwdg", properties=dict(_OKAY)))
        return nodes
