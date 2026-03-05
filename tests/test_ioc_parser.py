"""Tests for the IOC file parser."""

from pathlib import Path
import textwrap
import pytest

from mx2dts.ioc_parser import parse_ioc, IocFile, PinConfig


SAMPLE_IOC = textwrap.dedent("""\
    #MicroXplorer Configuration settings - do not modify
    File.Version=6
    Mcu.Family=STM32L4
    Mcu.IP0=NVIC
    Mcu.IP1=RCC
    Mcu.IP2=SYS
    Mcu.IP3=USART2
    Mcu.IPNb=4
    Mcu.Name=STM32L476R(C-E-G)Tx
    Mcu.Package=LQFP64
    Mcu.Pin0=PC13
    Mcu.Pin1=PC14/OSC32_IN
    Mcu.Pin2=PA2
    Mcu.Pin3=PA3
    Mcu.Pin4=VP_SYS_VS_Systick
    Mcu.PinsNb=5
    Mcu.UserName=STM32L476RGTx
    NVIC.BusFault_IRQn=true\\:0\\:0\\:false\\:false\\:true
    PA2.GPIOParameters=GPIO_Label,GPIO_Speed,GPIO_PuPd,GPIO_Mode
    PA2.GPIO_Label=USART_TX
    PA2.GPIO_Mode=GPIO_MODE_AF_PP
    PA2.GPIO_PuPd=GPIO_NOPULL
    PA2.Locked=true
    PA2.Mode=Asynchronous
    PA2.Signal=USART2_TX
    PA3.GPIOParameters=GPIO_Label,GPIO_Speed,GPIO_PuPd,GPIO_Mode
    PA3.GPIO_Label=USART_RX
    PA3.GPIO_Mode=GPIO_MODE_AF_PP
    PA3.Signal=USART2_RX
    PC13.Signal=GPIO_Input
    PC13.GPIO_Mode=GPIO_MODE_INPUT
    RCC.AHBFreq_Value=80000000
    RCC.APB1Freq_Value=80000000
    RCC.CortexFreq_Value=80000000
    RCC.PLLSourceVirtual=RCC_PLLSOURCE_HSI
    RCC.SYSCLKSource=RCC_SYSCLKSOURCE_PLLCLK
    RCC.PLLN=20
    USART2.BaudRate=115200
    USART2.WordLength=UART_WORDLENGTH_8B
    USART2.StopBits=UART_STOPBITS_1
    USART2.Parity=UART_PARITY_NONE
""")


@pytest.fixture
def ioc(tmp_path) -> IocFile:
    p = tmp_path / "test.ioc"
    p.write_text(SAMPLE_IOC)
    return parse_ioc(p)


def test_mcu_name(ioc):
    assert ioc.mcu_name == "STM32L476R(C-E-G)Tx"
    assert ioc.mcu_user_name == "STM32L476RGTx"
    assert ioc.mcu_family == "STM32L4"


def test_active_ips(ioc):
    assert ioc.active_ips == ["NVIC", "RCC", "SYS", "USART2"]


def test_pins(ioc):
    pins = ioc.pins
    # Virtual pin VP_SYS_VS_Systick should be excluded
    assert "VP_SYS_VS_Systick" not in pins
    # PC14/OSC32_IN → PC14
    assert "PA2" in pins
    assert "PA3" in pins

    pa2 = pins["PA2"]
    assert pa2.signal == "USART2_TX"
    assert pa2.label == "USART_TX"
    assert pa2.locked is True
    assert pa2.pinctrl_label == "usart2_tx_pa2"


def test_gpio_pins(ioc):
    gpio = ioc.gpio_pins()
    assert any(p.name == "PC13" for p in gpio)


def test_pins_for_peripheral(ioc):
    usart2_pins = ioc.pins_for_peripheral("USART2")
    assert len(usart2_pins) == 2
    signals = {p.signal for p in usart2_pins}
    assert signals == {"USART2_TX", "USART2_RX"}


def test_get_ip_params(ioc):
    params = ioc.get_ip_params("USART2")
    assert params["BaudRate"] == "115200"
    assert params["WordLength"] == "UART_WORDLENGTH_8B"


def test_nvic_colon_unescape(ioc):
    nvic = ioc.get_nvic()
    # \: should be unescaped to :
    assert ":" in nvic.get("BusFault_IRQn", "")


def test_rcc_freq(ioc):
    assert ioc.sys_clock_freq_hz == 80_000_000
    assert ioc.ahb_freq_hz == 80_000_000


def test_pin_skip_signals(ioc):
    pins = ioc.pins
    # PC13 has GPIO_Input signal — is_gpio should be True, not is_skip
    pc13 = pins.get("PC13")
    if pc13:
        assert pc13.is_gpio


def test_pinctrl_label_gpio(ioc):
    pa2 = ioc.pins["PA2"]
    assert pa2.pinctrl_label == "usart2_tx_pa2"
    pc13 = ioc.pins.get("PC13")
    if pc13:
        # GPIO pins have no pinctrl label
        assert pc13.pinctrl_label is None
