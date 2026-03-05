"""Tests for the DMA converter and dma_db lookup."""

from __future__ import annotations

import pytest

from tests.conftest import make_ioc, make_ctx
from mx2dts.converters.dma import DmaConverter, _compute_config_flags
from mx2dts.dma_db import get_dma_request, is_dmamux_family
from mx2dts.mcu_db import McuInfo, IpInfo


# ── config flag computation ───────────────────────────────────────────────────

def test_config_flags_all_default():
    entry = {
        "PeriphDataAlignment": "DMA_PDATAALIGN_BYTE",
        "MemDataAlignment":    "DMA_MDATAALIGN_BYTE",
        "PeriphInc":           "DMA_PINC_DISABLE",
        "MemInc":              "DMA_MINC_ENABLE",
    }
    flags = _compute_config_flags(entry)
    # periph 8b (0<<6)=0, mem 8b (0<<4)=0, periph-no-inc (1<<3)=8, mem-inc=0
    assert flags == "0x8"


def test_config_flags_16bit_both_inc():
    entry = {
        "PeriphDataAlignment": "DMA_PDATAALIGN_HALFWORD",
        "MemDataAlignment":    "DMA_MDATAALIGN_HALFWORD",
        "PeriphInc":           "DMA_PINC_ENABLE",
        "MemInc":              "DMA_MINC_ENABLE",
    }
    flags = _compute_config_flags(entry)
    # periph 16b = (1<<6)=64, mem 16b = (1<<4)=16 → 80 = 0x50
    assert flags == "0x50"


def test_config_flags_32bit_no_inc():
    entry = {
        "PeriphDataAlignment": "DMA_PDATAALIGN_WORD",
        "MemDataAlignment":    "DMA_MDATAALIGN_WORD",
        "PeriphInc":           "DMA_PINC_DISABLE",
        "MemInc":              "DMA_MINC_DISABLE",
    }
    flags = _compute_config_flags(entry)
    # periph 32b=(2<<6)=128, mem 32b=(2<<4)=32, periph-no-inc=(1<<3)=8, mem-no-inc=(1<<2)=4
    # total = 172 = 0xac
    assert flags == "0xac"


# ── dma_db family lookup ──────────────────────────────────────────────────────

def _make_mcu(family: str) -> McuInfo:
    return McuInfo(
        ref_name="TEST", family=family, line="", clock_tree=family,
        package="", core="", freq_mhz=0, ips=[], pins=[],
    )


def test_l4_usart2_rx_lookup():
    mcu = _make_mcu("STM32L4")
    req = get_dma_request("USART2_RX", "DMA1_Channel6", mcu)
    assert req == 2


def test_l4_usart2_tx_lookup():
    mcu = _make_mcu("STM32L4")
    req = get_dma_request("USART2_TX", "DMA1_Channel7", mcu)
    assert req == 2


def test_l4_spi1_rx_lookup():
    mcu = _make_mcu("STM32L4")
    req = get_dma_request("SPI1_RX", "DMA1_Channel2", mcu)
    assert req == 1


def test_g4_dmamux_usart1_rx():
    mcu = _make_mcu("STM32G4")
    # For DMAMUX, channel doesn't matter
    req = get_dma_request("USART1_RX", "DMA1_Channel1", mcu)
    assert req == 24


def test_unknown_signal_returns_none():
    mcu = _make_mcu("STM32L4")
    req = get_dma_request("UNKNOWN_SIGNAL", "DMA1_Channel1", mcu)
    assert req is None


def test_is_dmamux_family():
    assert is_dmamux_family("STM32G4") is True
    assert is_dmamux_family("STM32H7") is True
    assert is_dmamux_family("STM32L4") is False
    assert is_dmamux_family("STM32F4") is False
    assert is_dmamux_family("STM32F1") is False


# ── DMA converter ─────────────────────────────────────────────────────────────

def test_dma_converter_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=USART2
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        Dma.USART2_RX.0.Channel=DMA1_Channel6
        Dma.USART2_RX.0.Direction=DMA_PERIPH_TO_MEMORY
        Dma.USART2_RX.0.MemDataAlignment=DMA_MDATAALIGN_BYTE
        Dma.USART2_RX.0.MemInc=DMA_MINC_ENABLE
        Dma.USART2_RX.0.PeriphDataAlignment=DMA_PDATAALIGN_BYTE
        Dma.USART2_RX.0.PeriphInc=DMA_PINC_DISABLE
        Dma.USART2_RX.0.Priority=DMA_PRIORITY_LOW
        Dma.USART2_TX.0.Channel=DMA1_Channel7
        Dma.USART2_TX.0.Direction=DMA_MEMORY_TO_PERIPH
        Dma.USART2_TX.0.MemDataAlignment=DMA_MDATAALIGN_BYTE
        Dma.USART2_TX.0.MemInc=DMA_MINC_ENABLE
        Dma.USART2_TX.0.PeriphDataAlignment=DMA_PDATAALIGN_BYTE
        Dma.USART2_TX.0.PeriphInc=DMA_PINC_DISABLE
        Dma.USART2_TX.0.Priority=DMA_PRIORITY_LOW
    """)
    ctx = make_ctx(ioc, tmp_path)
    conv = DmaConverter()
    nodes = conv.convert(ctx)

    # Should emit &dma1 node
    assert any(n.ref == "&dma1" for n in nodes)

    # Should have peripheral_dma_props for usart2
    assert "usart2" in conv.peripheral_dma_props
    props = conv.peripheral_dma_props["usart2"]
    assert "dma-names" in props
    assert "rx" in props["dma-names"]
    assert "tx" in props["dma-names"]
    assert "dmas" in props
    # Request 2 for L4 USART2
    assert " 2 " in props["dmas"]


def test_dma_converter_bad_channel(tmp_path):
    """Malformed channel string should warn and skip."""
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=SPI1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        Dma.SPI1_RX.0.Channel=INVALID
        Dma.SPI1_RX.0.Direction=DMA_PERIPH_TO_MEMORY
        Dma.SPI1_RX.0.Priority=DMA_PRIORITY_LOW
    """)
    ctx = make_ctx(ioc, tmp_path)
    conv = DmaConverter()
    conv.convert(ctx)
    assert any("cannot parse channel" in w for w in ctx.warnings)
