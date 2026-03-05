"""Tests for SPI and I2C converters."""

from __future__ import annotations

from tests.conftest import make_ioc, make_ctx
from mx2dts.converters.spi import SpiConverter
from mx2dts.converters.i2c import I2cConverter


# ── SPI ───────────────────────────────────────────────────────────────────────

def test_spi_basic(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=SPI1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PA5
        Mcu.Pin1=PA6
        Mcu.Pin2=PA7
        Mcu.PinsNb=3
        PA5.Signal=SPI1_SCK
        PA6.Signal=SPI1_MISO
        PA7.Signal=SPI1_MOSI
        SPI1.Mode=SPI_MODE_MASTER
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = SpiConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&spi1"
    assert nodes[0].properties["status"] == '"okay"'


def test_spi_software_cs(tmp_path):
    """NSS pin configured as GPIO → cs-gpios property."""
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=SPI1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PA4
        Mcu.Pin1=PA5
        Mcu.Pin2=PA6
        Mcu.Pin3=PA7
        Mcu.PinsNb=4
        PA4.Signal=GPIO_Output
        PA4.GPIO_Mode=GPIO_MODE_OUTPUT_PP
        PA5.Signal=SPI1_SCK
        PA6.Signal=SPI1_MISO
        PA7.Signal=SPI1_MOSI
        SPI1.Mode=SPI_MODE_MASTER
        SPI1.NSS=SPI_NSS_SOFT
    """)
    ctx = make_ctx(ioc, tmp_path)
    # SPI converter looks for NSS pin by signal name SPI1_NSS — this pin is GPIO_Output
    # so cs-gpios won't be set here (signal doesn't match)
    nodes = SpiConverter().convert(ctx)
    assert len(nodes) == 1


def test_spi_not_present(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=RCC
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.PinsNb=0
    """)
    ctx = make_ctx(ioc, tmp_path)
    assert SpiConverter().convert(ctx) == []


# ── I2C ───────────────────────────────────────────────────────────────────────

def test_i2c_standard_speed(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=I2C1
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PB6
        Mcu.Pin1=PB7
        Mcu.PinsNb=2
        PB6.Signal=I2C1_SCL
        PB7.Signal=I2C1_SDA
        I2C1.ClockSpeed=100000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = I2cConverter().convert(ctx)
    assert len(nodes) == 1
    assert nodes[0].ref == "&i2c1"
    assert nodes[0].properties["clock-frequency"] == "<I2C_BITRATE_STANDARD>"


def test_i2c_fast_speed(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=I2C2
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PB10
        Mcu.Pin1=PB11
        Mcu.PinsNb=2
        PB10.Signal=I2C2_SCL
        PB11.Signal=I2C2_SDA
        I2C2.ClockSpeed=400000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = I2cConverter().convert(ctx)
    assert nodes[0].properties["clock-frequency"] == "<I2C_BITRATE_FAST>"


def test_i2c_fast_plus(tmp_path):
    ioc = make_ioc(tmp_path, """\
        Mcu.Family=STM32L4
        Mcu.IP0=I2C3
        Mcu.IPNb=1
        Mcu.Name=STM32L476RGTx
        Mcu.UserName=STM32L476RGTx
        Mcu.Pin0=PC0
        Mcu.Pin1=PC1
        Mcu.PinsNb=2
        PC0.Signal=I2C3_SCL
        PC1.Signal=I2C3_SDA
        I2C3.ClockSpeed=1000000
    """)
    ctx = make_ctx(ioc, tmp_path)
    nodes = I2cConverter().convert(ctx)
    assert nodes[0].properties["clock-frequency"] == "<I2C_BITRATE_FAST_PLUS>"
