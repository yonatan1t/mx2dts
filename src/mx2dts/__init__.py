"""mx2dts: Convert STM32CubeMX .ioc files to Zephyr DTS."""

from .ioc_parser import IocFile, parse_ioc
from .context import ConversionContext
from .dts_writer import generate_dts

__all__ = ["IocFile", "parse_ioc", "ConversionContext", "generate_dts"]
__version__ = "0.1.0"
