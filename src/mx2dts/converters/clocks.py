"""Clock configuration converter: IOC RCC settings → Zephyr clock DTS nodes."""

from __future__ import annotations

import re
from typing import Optional

from . import BaseConverter, DtsNode, _cell, _freq_macro
from ..context import ConversionContext


# Maps CubeMX prescaler macro names to integer divisors
_PRESCALER_MAP: dict[str, int] = {
    "RCC_SYSCLK_DIV1": 1,   "RCC_HCLK_DIV1": 1,
    "RCC_SYSCLK_DIV2": 2,   "RCC_HCLK_DIV2": 2,
    "RCC_SYSCLK_DIV4": 4,   "RCC_HCLK_DIV4": 4,
    "RCC_SYSCLK_DIV8": 8,   "RCC_HCLK_DIV8": 8,
    "RCC_SYSCLK_DIV16": 16, "RCC_HCLK_DIV16": 16,
    "RCC_SYSCLK_DIV64": 64,
    "RCC_SYSCLK_DIV128": 128,
    "RCC_SYSCLK_DIV256": 256,
    "RCC_SYSCLK_DIV512": 512,
}

# PLL multiplier macros for F1/F3-style PLL
_PLL_MUL_MAP: dict[str, int] = {f"RCC_PLL_MUL{n}": n for n in range(2, 17)}

# Clock source macro → Zephyr clock node reference
_CLK_SRC_MAP: dict[str, str] = {
    "RCC_SYSCLKSOURCE_HSI": "&clk_hsi",
    "RCC_SYSCLKSOURCE_HSE": "&clk_hse",
    "RCC_SYSCLKSOURCE_PLLCLK": "&pll",
    "RCC_SYSCLKSOURCE_MSI": "&clk_msi",
    "RCC_PLLSOURCE_HSI": "&clk_hsi",
    "RCC_PLLSOURCE_HSE": "&clk_hse",
    "RCC_PLLSOURCE_MSI": "&clk_msi",
    "RCC_PLLSOURCE_NONE": None,
}


class ClocksConverter(BaseConverter):
    """Generates clock-related DTS nodes from RCC configuration."""

    def convert(self, ctx: ConversionContext) -> list[DtsNode]:
        rcc = ctx.ioc.get_rcc()
        nodes: list[DtsNode] = []

        nodes.extend(self._oscillator_nodes(rcc, ctx))
        pll_node = self._pll_node(rcc, ctx)
        if pll_node:
            nodes.append(pll_node)
        rcc_node = self._rcc_node(rcc, ctx)
        if rcc_node:
            nodes.append(rcc_node)

        return nodes

    # ── Oscillator nodes ──────────────────────────────────────────────────────

    def _oscillator_nodes(self, rcc: dict, ctx: ConversionContext) -> list[DtsNode]:
        nodes = []
        sysclk_src = rcc.get("SYSCLKSource", "")
        pll_src = rcc.get("PLLSourceVirtual") or rcc.get("PLLSource", "")

        def osc_needed(clk_ref: str) -> bool:
            return clk_ref in (sysclk_src, pll_src)

        # HSI
        if osc_needed("RCC_SYSCLKSOURCE_HSI") or osc_needed("RCC_PLLSOURCE_HSI") or \
                "RCC_PLLSOURCE_HSI" in pll_src:
            nodes.append(DtsNode(ref="&clk_hsi", properties={"status": '"okay"'}))

        # HSE
        if osc_needed("RCC_SYSCLKSOURCE_HSE") or osc_needed("RCC_PLLSOURCE_HSE"):
            props = {"status": '"okay"'}
            hse_hz = _parse_hz(rcc.get("HSE_VALUE"))
            if hse_hz:
                props["clock-frequency"] = _cell(hse_hz)
            nodes.append(DtsNode(ref="&clk_hse", properties=props))

        # MSI
        if osc_needed("RCC_SYSCLKSOURCE_MSI") or osc_needed("RCC_PLLSOURCE_MSI"):
            props = {"status": '"okay"'}
            msi_hz = _parse_hz(rcc.get("MSI_VALUE"))
            if msi_hz:
                props["clock-frequency"] = _cell(msi_hz)
            nodes.append(DtsNode(ref="&clk_msi", properties=props))

        # LSI (for RTC, IWDG, etc.)
        lsi_users = {rcc.get(k, "") for k in ["RTCClockSelection", "IWDGClockSelection"]}
        if any("LSI" in s for s in lsi_users if s):
            nodes.append(DtsNode(ref="&clk_lsi", properties={"status": '"okay"'}))

        # LSE
        if any("LSE" in (rcc.get(k, "") or "") for k in ["RTCClockSelection", "RTCFreq"]):
            nodes.append(DtsNode(ref="&clk_lse", properties={"status": '"okay"'}))

        return nodes

    # ── PLL node ──────────────────────────────────────────────────────────────

    def _pll_node(self, rcc: dict, ctx: ConversionContext) -> Optional[DtsNode]:
        sysclk_src = rcc.get("SYSCLKSource", "")
        if "PLL" not in sysclk_src and "pll" not in sysclk_src.lower():
            return None

        props: dict[str, str] = {}

        pll_src_macro = rcc.get("PLLSourceVirtual") or rcc.get("PLLSource", "")
        clk_ref = _CLK_SRC_MAP.get(pll_src_macro)
        if clk_ref:
            props["clocks"] = _cell(clk_ref)

        # Integer dividers (L4/G4/H7/U5 style: M, N, R, Q, P)
        for cubemx_key, dts_prop in [
            ("PLLM", "div-m"),
            ("PLLN", "mul-n"),
            ("PLLP", "div-p"),
            ("PLLQ", "div-q"),
            ("PLLR", "div-r"),
        ]:
            val = rcc.get(cubemx_key)
            if val and val.isdigit():
                props[dts_prop] = _cell(int(val))

        # F1/F3 style: PLLMUL (RCC_PLL_MUL12 etc.)
        pll_mul_macro = rcc.get("PLLMUL", "")
        if pll_mul_macro in _PLL_MUL_MAP:
            props["mul-n"] = _cell(_PLL_MUL_MAP[pll_mul_macro])

        if not props:
            ctx.warn("PLL is selected as SYSCLK source but no PLL parameters found in IOC")
            return None

        props["status"] = '"okay"'
        return DtsNode(ref="&pll", properties=props)

    # ── RCC node ──────────────────────────────────────────────────────────────

    def _rcc_node(self, rcc: dict, ctx: ConversionContext) -> Optional[DtsNode]:
        props: dict[str, str] = {}

        sysclk_src = rcc.get("SYSCLKSource", "")
        clk_ref = _CLK_SRC_MAP.get(sysclk_src)
        if clk_ref:
            props["clocks"] = _cell(clk_ref)

        # Clock frequency
        freq_hz = ctx.ioc.sys_clock_freq_hz or ctx.ioc.ahb_freq_hz
        if freq_hz:
            props["clock-frequency"] = _freq_macro(freq_hz)

        # AHB / APB prescalers
        ahb = _prescaler_value(rcc.get("AHBCLKDivider", ""))
        if ahb is not None:
            props["ahb-prescaler"] = _cell(ahb)

        apb1 = _prescaler_value(rcc.get("APB1CLKDivider", ""))
        if apb1 is not None:
            props["apb1-prescaler"] = _cell(apb1)

        apb2 = _prescaler_value(rcc.get("APB2CLKDivider", ""))
        if apb2 is not None:
            props["apb2-prescaler"] = _cell(apb2)

        # If we derived frequencies but no divider macros exist, infer prescalers
        if "ahb-prescaler" not in props:
            props.update(self._infer_prescalers(rcc, freq_hz))

        if not props:
            return None

        return DtsNode(ref="&rcc", properties=props)

    def _infer_prescalers(self, rcc: dict, sys_hz: Optional[int]) -> dict[str, str]:
        """Infer AHB/APB prescalers from frequency ratios."""
        result: dict[str, str] = {}
        if not sys_hz:
            return result

        ahb_hz = _parse_hz(rcc.get("AHBFreq_Value") or rcc.get("HCLKFreq_Value"))
        apb1_hz = _parse_hz(rcc.get("APB1Freq_Value"))
        apb2_hz = _parse_hz(rcc.get("APB2Freq_Value"))

        if ahb_hz and sys_hz:
            div = _nearest_power_of_2(sys_hz // max(ahb_hz, 1))
            result["ahb-prescaler"] = _cell(div)

        if ahb_hz and apb1_hz:
            div = _nearest_power_of_2(ahb_hz // max(apb1_hz, 1))
            result["apb1-prescaler"] = _cell(div)

        if ahb_hz and apb2_hz:
            div = _nearest_power_of_2(ahb_hz // max(apb2_hz, 1))
            result["apb2-prescaler"] = _cell(div)

        return result


# ── Utilities ─────────────────────────────────────────────────────────────────

def _parse_hz(value: Optional[str]) -> Optional[int]:
    try:
        return int(float(value)) if value else None
    except (ValueError, TypeError):
        return None


def _prescaler_value(macro: str) -> Optional[int]:
    if not macro:
        return None
    if macro in _PRESCALER_MAP:
        return _PRESCALER_MAP[macro]
    # Try to extract a number from the macro name, e.g., "RCC_SYSCLK_DIV4" → 4
    m = re.search(r"(\d+)$", macro)
    if m:
        return int(m.group(1))
    return None


def _nearest_power_of_2(n: int) -> int:
    if n <= 1:
        return 1
    p = 1
    while p < n:
        p <<= 1
    return p
