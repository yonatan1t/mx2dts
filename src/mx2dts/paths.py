"""Auto-detect Zephyr and CubeMX database paths."""

from __future__ import annotations

import glob
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ZephyrPaths:
    zephyr_base: Path
    hal_stm32_dts: Path  # .../hal/stm32/dts/st/

    @property
    def soc_dts_root(self) -> Path:
        """Base for SoC DTSI includes: dts/arm/st/"""
        return self.zephyr_base / "dts" / "arm" / "st"


@dataclass
class CubeMXPaths:
    db_root: Path  # directory containing mcu/ and mcu/IP/ subdirs

    @property
    def mcu_dir(self) -> Path:
        return self.db_root / "mcu"

    @property
    def ip_dir(self) -> Path:
        return self.db_root / "mcu" / "IP"


def find_zephyr_paths(
    zephyr_base: Optional[Path] = None,
    hal_stm32: Optional[Path] = None,
) -> Optional[ZephyrPaths]:
    """Find Zephyr installation paths.

    Resolution order:
    1. Explicit arguments
    2. ZEPHYR_BASE / HAL_STM32 environment variables
    3. west workspace (via `west topdir`)
    4. Common install locations (~/zephyrproject, ~/ncs/*)
    """
    base = _resolve_zephyr_base(zephyr_base)
    if base is None:
        return None

    hal = _resolve_hal_stm32(hal_stm32, base)
    if hal is None:
        return None

    return ZephyrPaths(zephyr_base=base, hal_stm32_dts=hal)


def find_cubemx_db(db_path: Optional[Path] = None) -> Optional[CubeMXPaths]:
    """Find CubeMX database directory.

    Resolution order:
    1. Explicit argument
    2. CUBEMX_DB environment variable
    3. ~/STM32CubeMX/db/
    4. /opt/STM32CubeMX/db/
    5. WSL Windows paths: /mnt/c/Users/*/STM32CubeMX/db/
    6. Sibling directories containing db/mcu/STM32*.xml
    """
    if db_path is not None:
        p = Path(db_path)
        if _is_valid_cubemx_db(p):
            return CubeMXPaths(db_root=p)
        raise ValueError(f"Not a valid CubeMX DB directory: {p}")

    # Env var
    env = os.environ.get("CUBEMX_DB")
    if env:
        p = Path(env)
        if _is_valid_cubemx_db(p):
            return CubeMXPaths(db_root=p)

    candidates = [
        Path.home() / "STM32CubeMX" / "db",
        Path("/opt/STM32CubeMX/db"),
        Path("/opt/st/STM32CubeMX/db"),
    ]

    # WSL: scan Windows user profiles
    for mnt in [Path("/mnt/c"), Path("/mnt/d")]:
        users_dir = mnt / "Users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                candidates.append(user_dir / "STM32CubeMX" / "db")
                candidates.append(user_dir / "AppData" / "Local" / "STM32CubeMX" / "db")

    # Sibling directories that look like CubeMX databases
    cwd = Path.cwd()
    for parent in [cwd, cwd.parent, Path.home()]:
        for sibling in sorted(parent.iterdir()) if parent.exists() else []:
            if sibling.is_dir():
                candidates.append(sibling / "db")

    for candidate in candidates:
        if _is_valid_cubemx_db(candidate):
            return CubeMXPaths(db_root=candidate)

    return None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_zephyr_base(explicit: Optional[Path]) -> Optional[Path]:
    if explicit is not None:
        p = Path(explicit)
        if _is_valid_zephyr_base(p):
            return p
        raise ValueError(f"Not a valid Zephyr base: {p}")

    env = os.environ.get("ZEPHYR_BASE")
    if env:
        p = Path(env)
        if _is_valid_zephyr_base(p):
            return p

    # Try west topdir
    west_base = _west_zephyr_base()
    if west_base:
        return west_base

    # Common install locations
    for pattern in [
        str(Path.home() / "zephyrproject" / "zephyr"),
        str(Path.home() / "ncs" / "*" / "zephyr"),
        str(Path.home() / "ncs" / "zephyr"),
        "/opt/zephyrproject/zephyr",
    ]:
        matches = sorted(glob.glob(pattern), reverse=True)  # newest first
        for m in matches:
            p = Path(m)
            if _is_valid_zephyr_base(p):
                return p

    return None


def _resolve_hal_stm32(explicit: Optional[Path], zephyr_base: Path) -> Optional[Path]:
    if explicit is not None:
        p = Path(explicit)
        if _is_valid_hal_stm32(p):
            return p
        raise ValueError(f"Not a valid hal_stm32 dts/st directory: {p}")

    env = os.environ.get("HAL_STM32")
    if env:
        p = Path(env) / "dts" / "st"
        if _is_valid_hal_stm32(p):
            return p

    # west workspace: try to find hal_stm32 project
    west_hal = _west_hal_stm32_dts()
    if west_hal:
        return west_hal

    # Relative to zephyr_base (standard west workspace layout)
    for rel in [
        "../modules/hal/stm32/dts/st",
        "../../modules/hal/stm32/dts/st",
    ]:
        p = (zephyr_base / rel).resolve()
        if _is_valid_hal_stm32(p):
            return p

    # Common paths
    for pattern in [
        str(Path.home() / "zephyrproject" / "modules" / "hal" / "stm32" / "dts" / "st"),
        str(Path.home() / "ncs" / "*" / "modules" / "hal" / "stm32" / "dts" / "st"),
    ]:
        for m in sorted(glob.glob(pattern), reverse=True):
            p = Path(m)
            if _is_valid_hal_stm32(p):
                return p

    return None


def _is_valid_zephyr_base(p: Path) -> bool:
    return (p / "dts" / "arm" / "st").is_dir() and (p / "scripts" / "dts").is_dir()


def _is_valid_hal_stm32(p: Path) -> bool:
    return p.is_dir() and any(p.glob("*/stm32*.dtsi"))


def _is_valid_cubemx_db(p: Path) -> bool:
    return (p / "mcu").is_dir() and any((p / "mcu").glob("STM32*.xml"))


def _west_zephyr_base() -> Optional[Path]:
    try:
        result = subprocess.run(
            ["west", "list", "zephyr", "-f", "{abspath}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            p = Path(result.stdout.strip())
            if _is_valid_zephyr_base(p):
                return p
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _west_hal_stm32_dts() -> Optional[Path]:
    try:
        result = subprocess.run(
            ["west", "list", "hal_stm32", "-f", "{abspath}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            p = Path(result.stdout.strip()) / "dts" / "st"
            if _is_valid_hal_stm32(p):
                return p
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
