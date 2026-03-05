"""Tests for ADC, timers, CAN, USB, RTC, watchdog, RNG/CRC, SDMMC, QSPI, SAI, I2S, DCMI."""

from __future__ import annotations

import pytest
from tests.conftest import make_ioc, make_ctx
from mx2dts.converters.adc import AdcConverter
from mx2dts.converters.timers import TimersConverter
from mx2dts.converters.can import CanConverter
from mx2dts.converters.usb import UsbConverter
from mx2dts.converters.rtc import RtcConverter
from mx2dts.converters.watchdog import WatchdogConverter
from mx2dts.converters.rng_crc import RngConverter, CrcConverter
from mx2dts.converters.sdmmc import SdmmcConverter
from mx2dts.converters.qspi import QspiConverter
from mx2dts.converters.sai import SaiConverter
from mx2dts.converters.i2s import I2sConverter
from mx2dts.converters.dcmi import DcmiConverter


# ── ADC ───────────────────────────────────────────────────────────────────────

def test_adc_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=ADC1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PA0
        Mcu.PinsNb=1
        PA0.Signal=ADC1_IN5
        ADC1.ClockPrescaler=ADC_CLOCK_SYNC_PCLK_DIV4
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = AdcConverter().convert(ctx)
    assert len(nodes) == 1
    n = nodes[0]
    assert n.ref == "&adc1"
    assert n.properties["st,adc-clock-source"] == '"SYNC"'
    assert n.properties["st,adc-prescaler"] == "<4>"


def test_dac_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=DAC1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = AdcConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&dac1"


# ── Timers ────────────────────────────────────────────────────────────────────

def test_timer_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=TIM2
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        TIM2.Init.Prescaler=79
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = TimersConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&timers2"
    assert nodes[0].properties["st,prescaler"] == "<79>"


def test_timer_with_pwm(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=TIM3
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PB4
        Mcu.PinsNb=1
        PB4.Signal=TIM3_CH1
        TIM3.Init.Prescaler=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = TimersConverter().convert(ctx)
    assert len(nodes) == 1
    timer = nodes[0]
    assert len(timer.children) == 1
    assert "pwm3" in timer.children[0].ref


# ── CAN / FDCAN ───────────────────────────────────────────────────────────────

def test_can_with_apb1(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32F4
        Mcu.IP0=CAN1
        Mcu.IPNb=1
        Mcu.Name=STM32F407VGTx
        Mcu.UserName=STM32F407VGTx
        Mcu.PinsNb=0
        RCC.APB1Freq_Value=42000000
        CAN1.InitBitTimePrescaler=7
        CAN1.InitTimeSeg1=6
        CAN1.InitTimeSeg2=1
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = CanConverter().convert(ctx)
    assert len(nodes) == 1
    n = nodes[0]
    assert n.ref == "&can1"
    # bus-speed = 42000000 / (7 * (1+6+1)) = 750000
    assert n.properties["bus-speed"] == "<750000>"
    # sample-point = (1+6)*1000 / (1+6+1) = 875
    assert n.properties["sample-point"] == "<875>"


def test_can_no_apb1_warns(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32F4
        Mcu.IP0=CAN1
        Mcu.IPNb=1
        Mcu.Name=STM32F407VGTx
        Mcu.UserName=STM32F407VGTx
        Mcu.PinsNb=0
        CAN1.InitBitTimePrescaler=4
        CAN1.InitTimeSeg1=11
        CAN1.InitTimeSeg2=2
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = CanConverter().convert(ctx)
    assert len(nodes) == 1
    assert any("bus-speed" in w for w in ctx.warnings)


def test_fdcan(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32G4
        Mcu.IP0=FDCAN1
        Mcu.IPNb=1
        Mcu.Name=STM32G474RETx
        Mcu.UserName=STM32G474RETx
        Mcu.PinsNb=0
        FDCAN1.InitNominalBitRatePrescaler=8
        FDCAN1.InitNominalTimeSeg1=12
        FDCAN1.InitNominalTimeSeg2=2
        FDCAN1.InitDataBitRatePrescaler=2
        FDCAN1.InitDataTimeSeg1=12
        FDCAN1.InitDataTimeSeg2=2
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = CanConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&fdcan1"
    assert "bus-speed-data" in nodes[0].properties or any("bus-speed" in w for w in ctx.warnings)


# ── USB ───────────────────────────────────────────────────────────────────────

def test_usb_otg_fs(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=USB_OTG_FS
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        USB_OTG_FS.Speed=USB_OTG_FS_SPEED
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = UsbConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&usbotg_fs"
    assert nodes[0].properties.get("maximum-speed") == '"full-speed"'


# ── RTC ───────────────────────────────────────────────────────────────────────

def test_rtc_lse(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RTC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        RCC.RTCClockSelection=RCC_RTCCLKSOURCE_LSE
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = RtcConverter().convert(ctx)
    refs = [n.ref for n in nodes]
    assert "&rtc" in refs
    rtc = next(n for n in nodes if n.ref == "&rtc")
    assert rtc.properties.get("clocks") == "<&clk_lse>"
    # LSE enable node
    assert "&clk_lse" in refs


def test_rtc_lsi(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RTC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        RCC.RTCClockSelection=RCC_RTCCLKSOURCE_LSI
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = RtcConverter().convert(ctx)
    rtc = next(n for n in nodes if n.ref == "&rtc")
    assert rtc.properties.get("clocks") == "<&clk_lsi>"


# ── Watchdog ──────────────────────────────────────────────────────────────────

def test_iwdg(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=IWDG
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = WatchdogConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&iwdg"
    assert nodes[0].properties["status"] == '"okay"'


def test_wwdg(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=WWDG
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = WatchdogConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&wwdg"


def test_both_watchdogs(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=IWDG
        Mcu.IP1=WWDG
        Mcu.IPNb=2
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = WatchdogConverter().convert(ctx)
    assert len(nodes) == 2
    refs = {n.ref for n in nodes}
    assert refs == {"&iwdg", "&wwdg"}


# ── RNG / CRC ─────────────────────────────────────────────────────────────────

def test_rng(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RNG
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    assert len(RngConverter().convert(ctx)) == 1
    assert RngConverter().convert(ctx)[0].ref == "&rng"


def test_crc(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=CRC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    assert len(CrcConverter().convert(ctx)) == 1
    assert CrcConverter().convert(ctx)[0].ref == "&crc"


def test_rng_not_present(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    assert RngConverter().convert(ctx) == []
    assert CrcConverter().convert(ctx) == []


# ── SDMMC ─────────────────────────────────────────────────────────────────────

def test_sdmmc_4bit(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=SDMMC1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PC8
        Mcu.Pin1=PC9
        Mcu.Pin2=PC10
        Mcu.Pin3=PC11
        Mcu.PinsNb=4
        PC8.Signal=SDMMC1_D0
        PC9.Signal=SDMMC1_D1
        PC10.Signal=SDMMC1_D2
        PC11.Signal=SDMMC1_D3
        SDMMC1.ClockDiv=2
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = SdmmcConverter().convert(ctx)
    assert len(nodes) == 1
    n = nodes[0]
    assert n.ref == "&sdmmc1"
    assert n.properties["bus-width"] == "<4>"
    assert n.properties["clk-div"] == "<2>"


# ── QSPI ─────────────────────────────────────────────────────────────────────

def test_quadspi(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=QUADSPI
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        QUADSPI.ClockPrescaler=1
        QUADSPI.FlashSize=23
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = QspiConverter().convert(ctx)
    assert len(nodes) == 1
    n = nodes[0]
    assert n.ref == "&quadspi"
    assert n.properties["clock-prescaler"] == "<1>"
    assert n.properties["flash-size"] == "<23>"


# ── SAI ───────────────────────────────────────────────────────────────────────

def test_sai_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=SAI1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        SAI1.Protocol=SAI_I2S_STANDARD
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = SaiConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&sai1"
    assert nodes[0].properties["format"] == '"i2s"'


# ── I2S ───────────────────────────────────────────────────────────────────────

def test_i2s_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=I2S2
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        I2S2.Standard=I2S_STANDARD_PHILIPS
        I2S2.DataFormat=I2S_DATAFORMAT_16B
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = I2sConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&i2s2"
    assert nodes[0].properties["format"] == '"i2s_philips"'
    assert nodes[0].properties["word-size"] == "<16>"


# ── DCMI ─────────────────────────────────────────────────────────────────────

def test_dcmi_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32F4
        Mcu.IP0=DCMI
        Mcu.IPNb=1
        Mcu.Name=STM32F407VGTx
        Mcu.UserName=STM32F407VGTx
        Mcu.PinsNb=0
        DCMI.SynchroMode=DCMI_SYNCHRO_HARDWARE
        DCMI.HSPolarity=DCMI_HSPOLARITY_LOW
        DCMI.VSPolarity=DCMI_VSPOLARITY_LOW
        DCMI.PCKPolarity=DCMI_PCKPOLARITY_RISING
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = DcmiConverter().convert(ctx)
    assert len(nodes) == 1
    n = nodes[0]
    assert n.ref == "&dcmi"
    assert n.properties["hsync-active"] == "<0>"
    assert n.properties["vsync-active"] == "<0>"
    assert n.properties["pclk-sample"] == "<1>"
