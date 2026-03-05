"""Conversion context — holds all inputs and tracks warnings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ioc_parser import IocFile
from .mcu_db import McuInfo
from .paths import ZephyrPaths, CubeMXPaths
from .pinctrl_db import PinctrlDb


@dataclass
class ConversionContext:
    ioc: IocFile
    mcu: McuInfo
    zephyr: ZephyrPaths
    cubemx: CubeMXPaths
    pinctrl_db: PinctrlDb
    warnings: list[str] = field(default_factory=list)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def resolve_pinctrl_label(self, signal: str, pin: str) -> Optional[str]:
        """Resolve a pinctrl label, emitting a warning if not found."""
        label = self.pinctrl_db.resolve_label(self.mcu.ref_name, signal, pin)
        if label is None:
            # Try with user MCU name as well
            label = self.pinctrl_db.resolve_label(self.ioc.mcu_name, signal, pin)
        if label is None:
            self.warn(f"No pinctrl label found for signal '{signal}' on pin '{pin}'")
        return label

    @property
    def pinctrl_dtsi_include(self) -> Optional[str]:
        """The #include path for the pinctrl DTSI."""
        path = self.pinctrl_db.dtsi_include_path(self.mcu.ref_name)
        if path is None:
            path = self.pinctrl_db.dtsi_include_path(self.ioc.mcu_name)
        return path

    @property
    def soc_dtsi_include(self) -> Optional[str]:
        """The #include path for the SoC DTSI."""
        return _find_soc_dtsi_include(self.mcu, self.zephyr)


def _find_soc_dtsi_include(mcu: McuInfo, zephyr: ZephyrPaths) -> Optional[str]:
    """Find the SoC DTSI include path for the MCU.

    Returns a path like 'st/l4/stm32l476Xg.dtsi'.
    """
    family_dir = mcu.family_dir
    if not family_dir:
        return None

    soc_dir = zephyr.soc_dts_root / family_dir
    if not soc_dir.exists():
        return None

    # Extract MCU series (e.g., 'l476' from 'STM32L476RGTx')
    import re
    m = re.match(r"STM32([A-Z0-9]+?)([A-Z][A-Z0-9]*)$", mcu.ref_name, re.IGNORECASE)
    series = m.group(1).lower() if m else None

    # Extract flash size letter from user MCU name (e.g., 'G' from 'STM32L476RGTx')
    flash_code = _extract_flash_code(mcu.ref_name or mcu.clock_tree)

    if series:
        # Try stm32{series}X{flash}.dtsi  (e.g., stm32l476Xg.dtsi)
        if flash_code:
            for candidate in soc_dir.glob(f"stm32{series}*.dtsi"):
                stem = candidate.stem.lower()
                if flash_code.lower() in stem and stem.startswith(f"stm32{series}"):
                    return f"st/{family_dir}/{candidate.name}"

        # Try stm32{series}.dtsi base file
        base = soc_dir / f"stm32{series}.dtsi"
        if base.exists():
            return f"st/{family_dir}/{base.name}"

        # Best match: take the most specific file
        candidates = sorted(soc_dir.glob(f"stm32{series}*.dtsi"))
        if candidates:
            # Prefer files with flash code in name
            if flash_code:
                scored = [
                    (f.name.lower().count(flash_code.lower()), f)
                    for f in candidates
                ]
                scored.sort(reverse=True)
                return f"st/{family_dir}/{scored[0][1].name}"
            return f"st/{family_dir}/{candidates[-1].name}"

    return None


def _extract_flash_code(mcu_name: str) -> Optional[str]:
    """Extract flash size letter from MCU name.

    e.g., 'STM32L476RGTx' → 'G',  'STM32L476R(C-E-G)Tx' → None (ambiguous)
    """
    import re
    from .mcu_db import FLASH_SIZE_MAP
    # Look for the flash code in user MCU names (no parentheses)
    if "(" not in mcu_name:
        # Name like STM32L476RGTx: series(4) + pin_count(1) + flash(1) + package(1) + temp(1)
        # Flash code is a single letter: B,C,D,E,F,G,H,I,Z
        m = re.search(r"STM32\w+?([BCDEFGHIJKZ])[A-Z][a-z]", mcu_name, re.IGNORECASE)
        if m:
            code = m.group(1).upper()
            if code in FLASH_SIZE_MAP:
                return code
    return None
