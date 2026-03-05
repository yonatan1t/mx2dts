"""Look up DMA request numbers from the CubeMX IP XML database.

For pre-DMAMUX MCUs (F1, F2, F4, L1, L4 …) each DMA channel has a set of
fixed peripheral signal slots; the "request" is the CSELR nibble value that
selects the peripheral on a given channel.

For DMAMUX MCUs (G0, G4, H7, L5, U5, WB, WL …) any channel can carry any
signal; the "request" is the DMAMUX request-line number.

Resolution order for a (signal, channel) pair:
  1. CubeMX DMA IP XML  →  parsed table
  2. Embedded family tables (common MCU variants)
  3. None  →  caller should warn and emit 0
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .mcu_db import McuInfo
    from .paths import CubeMXPaths


# ── Embedded request tables ────────────────────────────────────────────────────
#
# Key:   (SIGNAL_UPPER, "DMAx_CHANNELy")  — channel is 1-indexed, upper-case
# Value: request / CSELR nibble
#
# Sources: STM32 reference manuals (DMA channel assignment tables) and
#          Zephyr board overlay examples.

# STM32F4 (DMA1 & DMA2, channel-selection via DMA_SxCR::CHSEL 3-bit)
_F4_TABLE: dict[tuple[str, str], int] = {
    # DMA1
    ("SPI3_RX",    "DMA1_CHANNEL0"): 0, ("SPI3_TX",    "DMA1_CHANNEL5"): 0,
    ("I2C1_TX",    "DMA1_CHANNEL6"): 1, ("I2C1_RX",    "DMA1_CHANNEL5"): 1,
    ("TIM7_UP",    "DMA1_CHANNEL4"): 1,
    ("SPI2_RX",    "DMA1_CHANNEL3"): 0, ("SPI2_TX",    "DMA1_CHANNEL4"): 0,
    ("USART3_TX",  "DMA1_CHANNEL3"): 4, ("USART3_RX",  "DMA1_CHANNEL1"): 4,
    ("UART4_RX",   "DMA1_CHANNEL2"): 4, ("UART4_TX",   "DMA1_CHANNEL4"): 4,
    ("USART2_RX",  "DMA1_CHANNEL5"): 4, ("USART2_TX",  "DMA1_CHANNEL6"): 4,
    ("I2C3_RX",    "DMA1_CHANNEL2"): 1, ("I2C3_TX",    "DMA1_CHANNEL4"): 1,
    ("I2S3_EXT_RX","DMA1_CHANNEL3"): 3, ("I2S3_EXT_TX","DMA1_CHANNEL5"): 3,
    ("I2S2_EXT_RX","DMA1_CHANNEL3"): 3, ("I2S2_EXT_TX","DMA1_CHANNEL4"): 3,
    ("TIM2_UP",    "DMA1_CHANNEL1"): 3, ("TIM2_CH1",   "DMA1_CHANNEL5"): 3,
    ("TIM2_CH2",   "DMA1_CHANNEL6"): 3, ("TIM2_CH3",   "DMA1_CHANNEL1"): 3,
    ("TIM2_CH4",   "DMA1_CHANNEL7"): 3,
    # DMA2
    ("SPI1_RX",    "DMA2_CHANNEL2"): 3, ("SPI1_TX",    "DMA2_CHANNEL3"): 3,
    ("USART1_RX",  "DMA2_CHANNEL2"): 4, ("USART1_TX",  "DMA2_CHANNEL7"): 4,
    ("USART6_RX",  "DMA2_CHANNEL1"): 5, ("USART6_TX",  "DMA2_CHANNEL6"): 5,
    ("ADC1",       "DMA2_CHANNEL0"): 0,
    ("SPI4_RX",    "DMA2_CHANNEL0"): 4, ("SPI4_TX",    "DMA2_CHANNEL1"): 4,
    ("SPI5_RX",    "DMA2_CHANNEL3"): 2, ("SPI5_TX",    "DMA2_CHANNEL4"): 2,
    ("I2C3_RX",    "DMA2_CHANNEL2"): 3,
}

# STM32L4 (DMA1 & DMA2, channel-selection via CSELR 4-bit per channel)
_L4_TABLE: dict[tuple[str, str], int] = {
    # DMA1
    ("ADC1",       "DMA1_CHANNEL1"): 0,
    ("SPI1_RX",    "DMA1_CHANNEL2"): 1, ("SPI1_TX",    "DMA1_CHANNEL3"): 1,
    ("SPI2_RX",    "DMA1_CHANNEL4"): 1, ("SPI2_TX",    "DMA1_CHANNEL5"): 1,
    ("USART3_TX",  "DMA1_CHANNEL2"): 2, ("USART3_RX",  "DMA1_CHANNEL3"): 2,
    ("USART1_TX",  "DMA1_CHANNEL4"): 2, ("USART1_RX",  "DMA1_CHANNEL5"): 2,
    ("USART2_RX",  "DMA1_CHANNEL6"): 2, ("USART2_TX",  "DMA1_CHANNEL7"): 2,
    ("I2C3_TX",    "DMA1_CHANNEL2"): 3, ("I2C3_RX",    "DMA1_CHANNEL3"): 3,
    ("I2C2_TX",    "DMA1_CHANNEL4"): 3, ("I2C2_RX",    "DMA1_CHANNEL5"): 3,
    ("I2C1_TX",    "DMA1_CHANNEL6"): 3, ("I2C1_RX",    "DMA1_CHANNEL7"): 3,
    ("TIM1_CH1",   "DMA1_CHANNEL2"): 7, ("TIM1_CH2",   "DMA1_CHANNEL3"): 7,
    ("TIM1_CH4",   "DMA1_CHANNEL4"): 7, ("TIM1_UP",    "DMA1_CHANNEL5"): 7,
    ("TIM1_TRIG",  "DMA1_CHANNEL4"): 7, ("TIM1_COM",   "DMA1_CHANNEL4"): 7,
    ("TIM1_CH3",   "DMA1_CHANNEL6"): 7,
    ("TIM2_UP",    "DMA1_CHANNEL2"): 4, ("TIM2_CH3",   "DMA1_CHANNEL1"): 4,
    ("TIM2_CH1",   "DMA1_CHANNEL5"): 4, ("TIM2_CH2",   "DMA1_CHANNEL7"): 4,
    ("TIM2_CH4",   "DMA1_CHANNEL7"): 4,
    ("TIM3_CH3",   "DMA1_CHANNEL2"): 5, ("TIM3_CH4",   "DMA1_CHANNEL3"): 5,
    ("TIM3_UP",    "DMA1_CHANNEL3"): 5, ("TIM3_CH1",   "DMA1_CHANNEL6"): 5,
    ("TIM3_TRIG",  "DMA1_CHANNEL6"): 5,
    # DMA2
    ("SPI3_RX",    "DMA2_CHANNEL1"): 3, ("SPI3_TX",    "DMA2_CHANNEL2"): 3,
    ("UART4_RX",   "DMA2_CHANNEL3"): 2, ("UART4_TX",   "DMA2_CHANNEL5"): 2,
    ("UART5_RX",   "DMA2_CHANNEL2"): 2, ("UART5_TX",   "DMA2_CHANNEL1"): 2,
    ("LPUART1_RX", "DMA2_CHANNEL7"): 4, ("LPUART1_TX", "DMA2_CHANNEL6"): 4,
    ("ADC2",       "DMA2_CHANNEL3"): 0, ("ADC3",       "DMA2_CHANNEL5"): 0,
    ("SDMMC1",     "DMA2_CHANNEL4"): 7, ("SDMMC1",     "DMA2_CHANNEL5"): 7,
    ("I2C4_RX",    "DMA2_CHANNEL1"): 0, ("I2C4_TX",    "DMA2_CHANNEL2"): 0,
    ("SAI1_A",     "DMA2_CHANNEL6"): 1, ("SAI1_B",     "DMA2_CHANNEL7"): 1,
    ("SAI2_A",     "DMA2_CHANNEL6"): 3, ("SAI2_B",     "DMA2_CHANNEL7"): 3,
    ("QUADSPI",    "DMA2_CHANNEL7"): 3,
}

# STM32G4 / STM32G0 — DMAMUX, request numbers from STM32G4 RM Table 91
_G4_TABLE: dict[tuple[str, str], int] = {
    # Channel doesn't matter for DMAMUX; key off signal only
    ("ADC1",      ""): 5,  ("ADC2",      ""): 36, ("ADC3",  ""): 37,
    ("ADC4",      ""): 38, ("ADC5",      ""): 39,
    ("DAC1_CH1",  ""): 6,  ("DAC1_CH2",  ""): 7,
    ("SPI1_RX",   ""): 10, ("SPI1_TX",   ""): 11,
    ("SPI2_RX",   ""): 12, ("SPI2_TX",   ""): 13,
    ("SPI3_RX",   ""): 14, ("SPI3_TX",   ""): 15,
    ("SPI4_RX",   ""): 74, ("SPI4_TX",   ""): 75,
    ("I2C1_RX",   ""): 16, ("I2C1_TX",   ""): 17,
    ("I2C2_RX",   ""): 18, ("I2C2_TX",   ""): 19,
    ("I2C3_RX",   ""): 20, ("I2C3_TX",   ""): 21,
    ("I2C4_RX",   ""): 22, ("I2C4_TX",   ""): 23,
    ("USART1_RX", ""): 24, ("USART1_TX", ""): 25,
    ("USART2_RX", ""): 26, ("USART2_TX", ""): 27,
    ("USART3_RX", ""): 28, ("USART3_TX", ""): 29,
    ("UART4_RX",  ""): 30, ("UART4_TX",  ""): 31,
    ("UART5_RX",  ""): 32, ("UART5_TX",  ""): 33,
    ("LPUART1_RX",""):  34, ("LPUART1_TX",""):  35,
    ("TIM1_CH1",  ""): 42, ("TIM1_CH2",  ""): 43,
    ("TIM1_CH3",  ""): 44, ("TIM1_CH4",  ""): 45,
    ("TIM1_UP",   ""): 46, ("TIM1_TRIG", ""): 47, ("TIM1_COM", ""): 48,
    ("TIM2_CH1",  ""): 56, ("TIM2_CH2",  ""): 57,
    ("TIM2_CH3",  ""): 58, ("TIM2_CH4",  ""): 59, ("TIM2_UP",  ""): 60,
    ("TIM3_CH1",  ""): 61, ("TIM3_CH2",  ""): 62,
    ("TIM3_CH3",  ""): 63, ("TIM3_CH4",  ""): 64, ("TIM3_UP",  ""): 65,
    ("QUADSPI",   ""): 9,
    ("SAI1_A",    ""): 2,  ("SAI1_B",    ""): 3,
    ("FDCAN1_INTR0", ""): 83, ("FDCAN1_INTR1", ""): 84,
}

# STM32H7 (DMAMUX1 for DMA1/DMA2, DMAMUX2 for BDMA) — RM0399 Table 110
_H7_TABLE: dict[tuple[str, str], int] = {
    ("ADC1",      ""): 9,  ("ADC2",      ""): 10, ("ADC3",  ""): 115,
    ("DAC1_CH1",  ""): 67, ("DAC1_CH2",  ""): 68,
    ("SPI1_RX",   ""): 37, ("SPI1_TX",   ""): 38,
    ("SPI2_RX",   ""): 39, ("SPI2_TX",   ""): 40,
    ("SPI3_RX",   ""): 61, ("SPI3_TX",   ""): 62,
    ("SPI4_RX",   ""): 83, ("SPI4_TX",   ""): 84,
    ("SPI5_RX",   ""): 85, ("SPI5_TX",   ""): 86,
    ("SPI6_RX",   ""): 87, ("SPI6_TX",   ""): 88,
    ("I2C1_RX",   ""): 33, ("I2C1_TX",   ""): 34,
    ("I2C2_RX",   ""): 35, ("I2C2_TX",   ""): 36,
    ("I2C3_RX",   ""): 73, ("I2C3_TX",   ""): 74,
    ("I2C4_RX",   ""): 82, ("I2C4_TX",   ""): 63,
    ("USART1_RX", ""): 41, ("USART1_TX", ""): 42,
    ("USART2_RX", ""): 43, ("USART2_TX", ""): 44,
    ("USART3_RX", ""): 45, ("USART3_TX", ""): 46,
    ("UART4_RX",  ""): 60, ("UART4_TX",  ""): 59,
    ("UART5_RX",  ""): 66, ("UART5_TX",  ""): 65,
    ("USART6_RX", ""): 71, ("USART6_TX", ""): 72,
    ("UART7_RX",  ""): 79, ("UART7_TX",  ""): 80,
    ("UART8_RX",  ""): 81, ("UART8_TX",  ""): 77,
    ("LPUART1_RX",""):  48, ("LPUART1_TX",""):  47,
    ("SDMMC1",    ""): 49, ("SDMMC2",    ""): 70,
    ("QUADSPI",   ""): 22,
    ("FDCAN1",    ""): 69,
    ("SAI1_A",    ""): 87, ("SAI1_B",    ""): 88,
    ("SAI2_A",    ""): 89, ("SAI2_B",    ""): 90,
}

# STM32F1 (no CSELR — request number is always 0 per channel, just need channel)
_F1_TABLE: dict[tuple[str, str], int] = {
    ("ADC1",       "DMA1_CHANNEL1"): 0, ("ADC3",       "DMA2_CHANNEL5"): 0,
    ("SPI1_RX",    "DMA1_CHANNEL2"): 0, ("SPI1_TX",    "DMA1_CHANNEL3"): 0,
    ("SPI2_RX",    "DMA1_CHANNEL4"): 0, ("SPI2_TX",    "DMA1_CHANNEL5"): 0,
    ("USART3_TX",  "DMA1_CHANNEL2"): 0, ("USART3_RX",  "DMA1_CHANNEL3"): 0,
    ("USART1_TX",  "DMA1_CHANNEL4"): 0, ("USART1_RX",  "DMA1_CHANNEL5"): 0,
    ("USART2_RX",  "DMA1_CHANNEL6"): 0, ("USART2_TX",  "DMA1_CHANNEL7"): 0,
    ("I2C2_TX",    "DMA1_CHANNEL4"): 0, ("I2C2_RX",    "DMA1_CHANNEL5"): 0,
    ("I2C1_TX",    "DMA1_CHANNEL6"): 0, ("I2C1_RX",    "DMA1_CHANNEL7"): 0,
    ("TIM1_CH1",   "DMA1_CHANNEL2"): 0, ("TIM1_CH4",   "DMA1_CHANNEL4"): 0,
    ("TIM1_UP",    "DMA1_CHANNEL5"): 0, ("TIM1_CH3",   "DMA1_CHANNEL6"): 0,
    ("TIM2_UP",    "DMA1_CHANNEL2"): 0, ("TIM2_CH3",   "DMA1_CHANNEL1"): 0,
    ("TIM2_CH1",   "DMA1_CHANNEL5"): 0, ("TIM2_CH2",   "DMA1_CHANNEL7"): 0,
    ("TIM3_CH3",   "DMA1_CHANNEL2"): 0, ("TIM3_CH4",   "DMA1_CHANNEL3"): 0,
    ("TIM3_UP",    "DMA1_CHANNEL3"): 0, ("TIM3_CH1",   "DMA1_CHANNEL6"): 0,
    ("TIM4_CH1",   "DMA1_CHANNEL1"): 0, ("TIM4_UP",    "DMA1_CHANNEL7"): 0,
    ("SPI3_RX",    "DMA2_CHANNEL1"): 0, ("SPI3_TX",    "DMA2_CHANNEL2"): 0,
    ("UART4_RX",   "DMA2_CHANNEL3"): 0, ("UART4_TX",   "DMA2_CHANNEL5"): 0,
    ("ADC2",       "DMA2_CHANNEL5"): 0,
}

# Map family prefix → (table, uses_dmamux)
_FAMILY_TABLES: list[tuple[str, dict, bool]] = [
    ("STM32F1", _F1_TABLE, False),
    ("STM32F4", _F4_TABLE, False),
    ("STM32L4", _L4_TABLE, False),
    ("STM32G4", _G4_TABLE, True),
    ("STM32G0", _G4_TABLE, True),   # G0 uses same DMAMUX scheme
    ("STM32H7", _H7_TABLE, True),
    ("STM32L5", _H7_TABLE, True),   # L5 DMAMUX request IDs very similar to H7
]


# ── Public API ─────────────────────────────────────────────────────────────────

def get_dma_request(
    signal: str,
    channel_str: str,
    mcu_info: "McuInfo",
    cubemx: Optional["CubeMXPaths"] = None,
) -> Optional[int]:
    """Return the DMA request/slot number for *signal* on *channel_str*.

    channel_str examples: ``"DMA1_Channel6"``, ``"DMA2_Channel3"``.

    Returns ``None`` when the mapping cannot be determined.
    """
    # Normalise channel_str: "DMA1_Channel6" → "DMA1_CHANNEL6"
    channel_norm = re.sub(r"(?i)channel", "CHANNEL", channel_str).upper()

    # 1. Try CubeMX IP XML
    if cubemx is not None:
        result = _lookup_ip_xml(signal, channel_norm, mcu_info, cubemx)
        if result is not None:
            return result

    # 2. Embedded family tables
    return _family_lookup(signal, channel_norm, mcu_info.family)


def is_dmamux_family(family: str) -> bool:
    """Return True if this MCU family uses DMAMUX (any-to-any DMA routing)."""
    for prefix, _, uses_mux in _FAMILY_TABLES:
        if family.upper().startswith(prefix.upper()):
            return uses_mux
    return False


# ── CubeMX IP XML lookup ───────────────────────────────────────────────────────

def _lookup_ip_xml(
    signal: str,
    channel_norm: str,
    mcu_info: "McuInfo",
    cubemx: "CubeMXPaths",
) -> Optional[int]:
    """Try to find and parse the DMA (or DMAMUX) IP XML for this MCU."""
    for ip in mcu_info.ips:
        if ip.name not in ("DMA", "DMAMUX"):
            continue
        xml_path = cubemx.ip_dir / f"{ip.name}-{ip.version}.xml"
        if not xml_path.exists():
            continue
        try:
            table = _parse_ip_xml(xml_path)
        except Exception:
            continue
        # DMAMUX: key without channel
        result = table.get((signal.upper(), channel_norm))
        if result is None:
            result = table.get((signal.upper(), ""))
        if result is not None:
            return result
    return None


def _parse_ip_xml(xml_path: Path) -> dict[tuple[str, str], int]:
    """Parse a CubeMX DMA or DMAMUX IP XML file.

    The XML schema varies across CubeMX versions.  We support two common
    layouts:

    Layout A (pre-DMAMUX, ``RefParameter`` with nested ``PossibleValue``):
      <RefParameter Name="Request" ...>
        <PossibleValue Value="DMA_REQUEST_USART2_RX" Comment="USART2_RX" .../>

    Layout B (DMAMUX, ``ModeLogicOperator`` / ``Mode`` tree):
      <ModeLogicOperator Name="...">
        <Mode Name="USART2_RX">
          ... <Signal Name="RequestNumber" Value="26"/> ...
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result: dict[tuple[str, str], int] = {}

    # Layout A: RefParameter/PossibleValue with numeric or named values
    for rp in root.iter("RefParameter"):
        if rp.get("Name", "") not in ("Request", "ChannelSrc", "RequestSrc"):
            continue
        for pv in rp.iter("PossibleValue"):
            value = pv.get("Value", "")
            comment = pv.get("Comment", "") or pv.get("Semaphore", "")
            num = _extract_number(value)
            if num is None:
                continue
            # Comment often contains "SIGNAL_NAME / Channel Y"
            for sig in _extract_signals(comment or value):
                result[(sig.upper(), "")] = num

    # Layout B: nested Mode tree with SignalName / RequestNumber
    for mode_el in root.iter("Mode"):
        name = mode_el.get("Name", "")
        # Look for child Signal elements with RequestNumber
        for sig_el in mode_el.iter("Signal"):
            if sig_el.get("Name", "").upper() in ("REQUESTNUMBER", "REQUEST_NB", "REQUEST"):
                num = _extract_number(sig_el.get("Value", ""))
                if num is not None:
                    for sig in _extract_signals(name):
                        result[(sig.upper(), "")] = num

    return result


def _extract_number(s: str) -> Optional[int]:
    """Extract an integer from a string like '26', 'DMA_REQUEST_26', etc."""
    m = re.search(r"\b(\d+)\b", s)
    return int(m.group(1)) if m else None


def _extract_signals(text: str) -> list[str]:
    """Extract signal names from a CubeMX comment like 'USART2_RX / USART2_TX'."""
    # Split on '/' or ','
    parts = re.split(r"[/,]", text)
    signals = []
    for part in parts:
        part = part.strip()
        # Signal names look like WORD_WORD (uppercase with underscores)
        m = re.match(r"^([A-Z][A-Z0-9]+(?:_[A-Z][A-Z0-9]*)+)$", part.upper())
        if m:
            signals.append(m.group(1))
    return signals


# ── Embedded family lookup ─────────────────────────────────────────────────────

def _family_lookup(
    signal: str,
    channel_norm: str,
    family: str,
) -> Optional[int]:
    sig_up = signal.upper()
    for prefix, table, uses_mux in _FAMILY_TABLES:
        if not family.upper().startswith(prefix.upper()):
            continue
        if uses_mux:
            # DMAMUX: channel doesn't matter
            return table.get((sig_up, ""))
        else:
            # Pre-DMAMUX: need exact channel
            val = table.get((sig_up, channel_norm))
            if val is not None:
                return val
            # Try without the leading "DMA" prefix on channel
            short = re.sub(r"^DMA\d+_", "", channel_norm)
            return table.get((sig_up, short))
    return None
