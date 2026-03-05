"""Tests for the serial (USART/UART/LPUART) converter."""

from __future__ import annotations

import textwrap
import pytest

from mx2dts.converters.serial import SerialConverter
from tests.conftest import make_ioc, make_ctx


def test_usart_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=USART2
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PA2
        Mcu.Pin1=PA3
        Mcu.PinsNb=2
        PA2.Signal=USART2_TX
        PA3.Signal=USART2_RX
        USART2.BaudRate=115200
        USART2.WordLength=UART_WORDLENGTH_8B
        USART2.StopBits=UART_STOPBITS_1
        USART2.Parity=UART_PARITY_NONE
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = SerialConverter().convert(ctx)
    assert len(nodes) == 1
    node = nodes[0]
    assert node.ref == "&usart2"
    assert node.properties["current-speed"] == "<115200>"
    assert node.properties["status"] == '"okay"'
    # no parity/stop-bits emitted for defaults
    assert "parity" not in node.properties
    assert "stop-bits" not in node.properties
    assert "data-bits" not in node.properties


def test_usart_non_default_params(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=USART3
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PB10
        Mcu.Pin1=PB11
        Mcu.PinsNb=2
        PB10.Signal=USART3_TX
        PB11.Signal=USART3_RX
        USART3.BaudRate=9600
        USART3.WordLength=UART_WORDLENGTH_7B
        USART3.StopBits=UART_STOPBITS_2
        USART3.Parity=UART_PARITY_ODD
        USART3.HwFlowCtl=UART_HWCONTROL_RTS_CTS
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = SerialConverter().convert(ctx)
    assert len(nodes) == 1
    p = nodes[0].properties
    assert p["current-speed"] == "<9600>"
    assert p["parity"] == '"odd"'
    assert p["stop-bits"] == '"2"'
    assert p["data-bits"] == "<7>"
    assert p["hw-flow-control"] == "true"


def test_lpuart(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=LPUART1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PG7
        Mcu.Pin1=PG8
        Mcu.PinsNb=2
        PG7.Signal=LPUART1_TX
        PG8.Signal=LPUART1_RX
        LPUART1.BaudRate=115200
        LPUART1.Parity=UART_PARITY_NONE
        LPUART1.StopBits=UART_STOPBITS_1
        LPUART1.WordLength=UART_WORDLENGTH_8B
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = SerialConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&lpuart1"


def test_no_serial_ips(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    assert SerialConverter().convert(ctx) == []
