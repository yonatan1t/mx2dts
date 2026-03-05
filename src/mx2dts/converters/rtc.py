"""RTC converter: RTC instance → Zephyr DTS nodes."""

from __future__ import annotations

from . import BaseConverter, DtsNode, _cell
from ..context import ConversionContext


# Maps RTCClockSelection macro → (Zephyr clock ref, warn_hse)
_RTC_CLK_MAP: dict[str, tuple[str, bool]] = {
    "RCC_RTCCLKSOURCE_LSE":      ("&clk_lse", False),
    "RCC_RTCCLKSOURCE_LSI":      ("&clk_lsi", False),
    "RCC_RTCCLKSOURCE_HSE_DIVX": ("&clk_hse", True),
    "RCC_RTCCLKSOURCE_HSE_DIV32":("&clk_hse", True),
}


class RtcConverter(BaseConverter):
    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        if not ctx.ioc.has_ip("RTC"):
            return []

        nodes: list[DtsNode] = []

        clk_node = self._clock_enable_node(ctx)
        if clk_node:
            nodes.append(clk_node)

        nodes.append(self._rtc_node(ctx))

        if ctx.ioc.has_ip("TAMP"):
            nodes.append(DtsNode(ref="&tamp", properties={"status": '"okay"'}))

        return nodes

    def _rtc_node(self, ctx: ConversionContext) -> DtsNode:
        rcc = ctx.ioc.get_rcc()
        clk_sel = rcc.get("RTCClockSelection", "")

        props: dict[str, str] = {}

        entry = _RTC_CLK_MAP.get(clk_sel)
        if entry:
            clk_ref, warn_hse = entry
            props["clocks"] = _cell(clk_ref)
            if warn_hse:
                ctx.warn(
                    "RTC clock source is HSE — verify the HSE divisor and "
                    "set the 'clocks' property manually if needed"
                )
        elif clk_sel:
            # Unknown / not mapped — warn and skip clocks property
            ctx.warn(
                f"RTC: unrecognised RTCClockSelection '{clk_sel}'; "
                "'clocks' property not emitted"
            )

        props["status"] = '"okay"'
        return DtsNode(ref="&rtc", properties=props)

    def _clock_enable_node(self, ctx: ConversionContext) -> DtsNode | None:
        """Return a clock-enable node when the RTC uses LSE (most common case)."""
        rcc = ctx.ioc.get_rcc()
        clk_sel = rcc.get("RTCClockSelection", "")
        if clk_sel == "RCC_RTCCLKSOURCE_LSE":
            return DtsNode(ref="&clk_lse", properties={"status": '"okay"'})
        return None
