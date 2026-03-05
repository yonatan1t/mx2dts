"""Shared pytest fixtures for mx2dts tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mx2dts.ioc_parser import parse_ioc, IocFile
from mx2dts.mcu_db import McuInfo, IpInfo, PinInfo, PinSignal
from mx2dts.paths import ZephyrPaths, CubeMXPaths
from mx2dts.pinctrl_db import PinctrlDb
from mx2dts.context import ConversionContext


# ── Minimal IOC content ───────────────────────────────────────────────────────

MINIMAL_IOC = textwrap.dedent("""\
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
    Mcu.Pin0=PA2
    Mcu.Pin1=PA3
    Mcu.PinsNb=2
    Mcu.UserName=STM32L476RGTx
    PA2.Signal=USART2_TX
    PA2.GPIO_Label=USART_TX
    PA2.GPIO_Mode=GPIO_MODE_AF_PP
    PA2.GPIO_PuPd=GPIO_NOPULL
    PA2.Locked=true
    PA3.Signal=USART2_RX
    PA3.GPIO_Label=USART_RX
    PA3.GPIO_Mode=GPIO_MODE_AF_PP
    RCC.AHBFreq_Value=80000000
    RCC.APB1Freq_Value=80000000
    RCC.APB2Freq_Value=80000000
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
def ioc_path(tmp_path) -> Path:
    p = tmp_path / "test.ioc"
    p.write_text(MINIMAL_IOC)
    return p


@pytest.fixture
def ioc(ioc_path) -> IocFile:
    return parse_ioc(ioc_path)


@pytest.fixture
def mock_mcu() -> McuInfo:
    return McuInfo(
        ref_name="STM32L476RGTx",
        family="STM32L4",
        line="STM32L4x6",
        clock_tree="STM32L4",
        package="LQFP64",
        core="Arm Cortex-M4",
        freq_mhz=80,
        ips=[
            IpInfo("USART2", "USART", "STM32L4x6_usart_v2"),
            IpInfo("DMA1",   "DMA",   "STM32L4x6_dma_v2"),
            IpInfo("RCC",    "RCC",   "STM32L4x6_rcc_v1"),
        ],
        pins=[
            PinInfo("PA2", "29", "I/O", [PinSignal("USART2_TX")]),
            PinInfo("PA3", "30", "I/O", [PinSignal("USART2_RX")]),
        ],
    )


@pytest.fixture
def mock_zephyr(tmp_path) -> ZephyrPaths:
    """Fake Zephyr paths pointing to a temp directory."""
    base = tmp_path / "zephyr"
    hal  = tmp_path / "hal_stm32" / "dts" / "st"
    (base / "dts" / "arm" / "st").mkdir(parents=True)
    (base / "scripts" / "dts").mkdir(parents=True)
    hal.mkdir(parents=True)
    return ZephyrPaths(zephyr_base=base, hal_stm32_dts=hal)


@pytest.fixture
def mock_cubemx(tmp_path) -> CubeMXPaths:
    db = tmp_path / "cubemx" / "db"
    (db / "mcu" / "IP").mkdir(parents=True)
    return CubeMXPaths(db_root=db)


@pytest.fixture
def pinctrl_db(mock_zephyr) -> PinctrlDb:
    return PinctrlDb(mock_zephyr.hal_stm32_dts)


@pytest.fixture
def ctx(ioc, mock_mcu, mock_zephyr, mock_cubemx, pinctrl_db) -> ConversionContext:
    return ConversionContext(
        ioc=ioc,
        mcu=mock_mcu,
        zephyr=mock_zephyr,
        cubemx=mock_cubemx,
        pinctrl_db=pinctrl_db,
    )


def make_ioc(tmp_path: Path, content: str) -> IocFile:
    """Helper: write content to a temp .ioc file and parse it."""
    p = tmp_path / "board.ioc"
    p.write_text(textwrap.dedent(content))
    return parse_ioc(p)


def make_ctx(ioc: IocFile, tmp_path: Path, extra_ips: list[IpInfo] | None = None) -> ConversionContext:
    """Helper: build a ConversionContext with a mock MCU for the given IocFile."""
    ips = [
        IpInfo("RCC",  "RCC",  "v1"),
        IpInfo("DMA1", "DMA",  "STM32L4x6_dma_v2"),
    ] + (extra_ips or [])

    mcu = McuInfo(
        ref_name="STM32L476RGTx",
        family="STM32L4",
        line="STM32L4x6",
        clock_tree="STM32L4",
        package="LQFP64",
        core="Arm Cortex-M4",
        freq_mhz=80,
        ips=ips,
        pins=[],
    )

    zbase = tmp_path / "zephyr"
    hal   = tmp_path / "hal" / "dts" / "st"
    (zbase / "dts" / "arm" / "st").mkdir(parents=True)
    (zbase / "scripts" / "dts").mkdir(parents=True)
    hal.mkdir(parents=True)

    db = tmp_path / "db"
    (db / "mcu" / "IP").mkdir(parents=True)

    return ConversionContext(
        ioc=ioc,
        mcu=mcu,
        zephyr=ZephyrPaths(zephyr_base=zbase, hal_stm32_dts=hal),
        cubemx=CubeMXPaths(db_root=db),
        pinctrl_db=PinctrlDb(hal),
    )
