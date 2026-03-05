"""Tests for the GPIO converter."""

from __future__ import annotations

from tests.conftest import make_ioc, make_ctx
from mx2dts.converters.gpio import GpioConverter


def test_gpio_output_becomes_led(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PA5
        Mcu.PinsNb=1
        PA5.Signal=GPIO_Output
        PA5.GPIO_Mode=GPIO_MODE_OUTPUT_PP
        PA5.GPIO_Label=LED1
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = GpioConverter().convert(ctx)
    assert any(n.ref == "leds" for n in nodes)
    leds = next(n for n in nodes if n.ref == "leds")
    assert len(leds.children) == 1
    child = leds.children[0]
    assert "led1" in child.ref
    assert "&gpioa 5" in child.properties["gpios"]


def test_gpio_input_becomes_key(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PC13
        Mcu.PinsNb=1
        PC13.Signal=GPIO_Input
        PC13.GPIO_Mode=GPIO_MODE_INPUT
        PC13.GPIO_Label=USER_BTN
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = GpioConverter().convert(ctx)
    assert any(n.ref == "gpio_keys" for n in nodes)
    keys = next(n for n in nodes if n.ref == "gpio_keys")
    assert len(keys.children) == 1


def test_gpio_pullup_active_low(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PB2
        Mcu.PinsNb=1
        PB2.Signal=GPIO_Input
        PB2.GPIO_Mode=GPIO_MODE_INPUT
        PB2.GPIO_PuPd=GPIO_PULLUP
        PB2.GPIO_Label=BTN
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = GpioConverter().convert(ctx)
    keys = next(n for n in nodes if n.ref == "gpio_keys")
    assert "GPIO_ACTIVE_LOW" in keys.children[0].properties["gpios"]


def test_no_gpio_pins(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PA2
        Mcu.PinsNb=1
        PA2.Signal=USART2_TX
    """)
    ctx = make_ctx(ioc, tmp_path)
    assert GpioConverter().convert(ctx) == []
