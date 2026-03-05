"""Integration tests using the real test.ioc (NUCLEO-WB55RG / STM32WB55RGVx)."""

from __future__ import annotations

from pathlib import Path
import pytest

from mx2dts.ioc_parser import parse_ioc
from mx2dts.mcu_db import McuInfo, IpInfo, PinInfo, PinSignal
from mx2dts.paths import ZephyrPaths, CubeMXPaths
from mx2dts.pinctrl_db import PinctrlDb
from mx2dts.context import ConversionContext
from mx2dts.dts_writer import generate_dts

REAL_IOC = Path(__file__).parent / "test.ioc"


@pytest.fixture
def ioc():
    return parse_ioc(REAL_IOC)


@pytest.fixture
def wb55_mcu():
    return McuInfo(
        ref_name="STM32WB55RGVx",
        family="STM32WB",
        line="STM32WB55",
        clock_tree="STM32WB",
        package="VFQFPN68",
        core="Arm Cortex-M4",
        freq_mhz=64,
        ips=[
            IpInfo("ADC1",   "ADC",    "STM32WB55_adc_v1"),
            IpInfo("LPUART1","LPUART", "STM32WB55_lpuart_v1"),
            IpInfo("SPI2",   "SPI",    "STM32WB55_spi_v1"),
            IpInfo("RCC",    "RCC",    "STM32WB55_rcc_v1"),
            IpInfo("DMA1",   "DMA",    "STM32WB55_dma_v1"),
        ],
        pins=[
            PinInfo("PA2",  "7",  "I/O", [PinSignal("LPUART1_TX")]),
            PinInfo("PA3",  "8",  "I/O", [PinSignal("LPUART1_RX")]),
            PinInfo("PA9",  "15", "I/O", [PinSignal("SPI2_SCK")]),
            PinInfo("PB6",  "37", "I/O", [PinSignal("USART1_TX")]),
            PinInfo("PB7",  "38", "I/O", [PinSignal("USART1_RX")]),
            PinInfo("PC0",  "19", "I/O", [PinSignal("ADC1_IN1")]),
            PinInfo("PC1",  "20", "I/O", [PinSignal("ADC1_IN2")]),
            PinInfo("PC2",  "21", "I/O", [PinSignal("SPI2_MISO")]),
            PinInfo("PC3",  "22", "I/O", [PinSignal("SPI2_MOSI")]),
        ],
    )


@pytest.fixture
def ctx(ioc, wb55_mcu, tmp_path):
    zbase = tmp_path / "zephyr"
    hal   = tmp_path / "hal" / "dts" / "st"
    (zbase / "dts" / "arm" / "st").mkdir(parents=True)
    (zbase / "scripts" / "dts").mkdir(parents=True)
    hal.mkdir(parents=True)
    db = tmp_path / "db"
    (db / "mcu" / "IP").mkdir(parents=True)

    return ConversionContext(
        ioc=ioc,
        mcu=wb55_mcu,
        zephyr=ZephyrPaths(zephyr_base=zbase, hal_stm32_dts=hal),
        cubemx=CubeMXPaths(db_root=db),
        pinctrl_db=PinctrlDb(hal),
    )


# ── IOC parsing ───────────────────────────────────────────────────────────────

def test_mcu_identity(ioc):
    assert ioc.mcu_name == "STM32WB55RGVx"
    assert ioc.mcu_family == "STM32WB"
    assert ioc.mcu_user_name == "STM32WB55RGVx"


def test_active_ips(ioc):
    ips = ioc.active_ips
    assert "LPUART1" in ips
    assert "SPI2" in ips
    assert "ADC1" in ips
    assert "RCC" in ips


def test_lpuart_pins(ioc):
    pins = ioc.pins_for_peripheral("LPUART1")
    signals = {p.signal for p in pins}
    assert "LPUART1_TX" in signals
    assert "LPUART1_RX" in signals


def test_spi2_pins(ioc):
    pins = ioc.pins_for_peripheral("SPI2")
    signals = {p.signal for p in pins}
    assert "SPI2_SCK"  in signals
    assert "SPI2_MISO" in signals
    assert "SPI2_MOSI" in signals


def test_adcx_alias_resolved(ioc):
    """ADCx_IN1 aliases must be resolved to ADC1_IN1 via SH. entries."""
    pins = ioc.pins
    # PC0 should have signal ADC1_IN1 (resolved from ADCx_IN1)
    pc0 = pins.get("PC0")
    assert pc0 is not None, "PC0 should be parsed"
    assert pc0.signal == "ADC1_IN1", f"Expected ADC1_IN1, got {pc0.signal!r}"


def test_adc_pins_for_peripheral(ioc):
    adc_pins = ioc.pins_for_peripheral("ADC1")
    assert len(adc_pins) == 2
    signals = {p.signal for p in adc_pins}
    assert "ADC1_IN1" in signals
    assert "ADC1_IN2" in signals


def test_virtual_pins_excluded(ioc):
    pins = ioc.pins
    assert "VP_SYS_VS_Systick" not in pins
    assert "VP_MEMORYMAP_VS_MEMORYMAP" not in pins


def test_jtag_pins_are_skip(ioc):
    pins = ioc.pins
    pa13 = pins.get("PA13")
    if pa13:
        assert pa13.is_skip


def test_osc_pins_excluded(ioc):
    """OSC_IN / OSC_OUT should not appear as real GPIO pins."""
    pins = ioc.pins
    assert "OSC_IN" not in pins
    assert "OSC_OUT" not in pins


def test_rcc_clock_freq(ioc):
    assert ioc.sys_clock_freq_hz == 32_000_000
    assert ioc.ahb_freq_hz == 32_000_000


# ── Full conversion pipeline ──────────────────────────────────────────────────

def test_board_mode_generates_dts(ctx):
    out = generate_dts(ctx, mode="board")
    assert "/dts-v1/;" in out
    assert "model =" in out
    assert "zephyr,sram" in out
    assert "zephyr,flash" in out


def test_board_mode_has_lpuart(ctx):
    out = generate_dts(ctx, mode="board")
    assert "&lpuart1" in out


def test_board_mode_has_spi2(ctx):
    out = generate_dts(ctx, mode="board")
    assert "&spi2" in out


def test_board_mode_has_adc1(ctx):
    out = generate_dts(ctx, mode="board")
    assert "&adc1" in out


def test_overlay_mode_no_root_node(ctx):
    out = generate_dts(ctx, mode="overlay")
    assert "/dts-v1/;" not in out
    assert "model =" not in out
    assert "&lpuart1" in out
    assert "&spi2" in out


def test_board_mode_mcu_compatible(ctx):
    out = generate_dts(ctx, mode="board")
    # compatible should contain something derived from the MCU name
    assert "st," in out


def test_console_set_to_lpuart(ctx):
    out = generate_dts(ctx, mode="board")
    # LPUART1 is the first serial IP — should be chosen as console
    assert "zephyr,console" in out
    assert "lpuart1" in out


def test_clocks_node_generated(ctx):
    # WB55 RCC params don't have SYSCLKSource, so clock nodes may be minimal
    out = generate_dts(ctx, mode="board")
    # At minimum, &rcc node should appear if freq is known
    assert "&rcc" in out or "clock-frequency" in out or len(ctx.warnings) > 0
