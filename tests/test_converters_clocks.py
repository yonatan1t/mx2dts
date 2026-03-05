"""Tests for the ClocksConverter."""

from __future__ import annotations

from tests.conftest import make_ioc, make_ctx
from mx2dts.converters.clocks import ClocksConverter


def test_pll_from_hsi(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        RCC.SYSCLKSource=RCC_SYSCLKSOURCE_PLLCLK
        RCC.PLLSourceVirtual=RCC_PLLSOURCE_HSI
        RCC.PLLN=20
        RCC.PLLM=1
        RCC.PLLR=2
        RCC.CortexFreq_Value=80000000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = ClocksConverter().convert(ctx)
    refs = [n.ref for n in nodes]
    assert "&clk_hsi" in refs
    assert "&pll" in refs
    assert "&rcc" in refs

    pll = next(n for n in nodes if n.ref == "&pll")
    assert pll.properties["mul-n"] == "<20>"
    assert pll.properties["div-m"] == "<1>"
    assert pll.properties["div-r"] == "<2>"
    assert pll.properties.get("clocks") == "<&clk_hsi>"


def test_hse_direct(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32F4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32F407VGTx
        Mcu.UserName=STM32F407VGTx
        Mcu.PinsNb=0
        RCC.SYSCLKSource=RCC_SYSCLKSOURCE_HSE
        RCC.HSE_VALUE=8000000
        RCC.CortexFreq_Value=8000000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = ClocksConverter().convert(ctx)
    refs = [n.ref for n in nodes]
    assert "&clk_hse" in refs
    hse = next(n for n in nodes if n.ref == "&clk_hse")
    assert hse.properties["clock-frequency"] == "<8000000>"


def test_rcc_freq_macro(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        RCC.SYSCLKSource=RCC_SYSCLKSOURCE_PLLCLK
        RCC.PLLSourceVirtual=RCC_PLLSOURCE_HSI
        RCC.PLLN=20
        RCC.CortexFreq_Value=80000000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = ClocksConverter().convert(ctx)
    rcc = next(n for n in nodes if n.ref == "&rcc")
    assert rcc.properties["clock-frequency"] == "<DT_FREQ_M(80)>"


def test_lsi_for_rtc(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
        RCC.SYSCLKSource=RCC_SYSCLKSOURCE_HSI
        RCC.RTCClockSelection=RCC_RTCCLKSOURCE_LSI
        RCC.CortexFreq_Value=16000000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = ClocksConverter().convert(ctx)
    refs = [n.ref for n in nodes]
    assert "&clk_lsi" in refs
