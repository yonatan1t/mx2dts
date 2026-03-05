"""Read STM32 MCU information from the CubeMX database."""

from __future__ import annotations

import fnmatch
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_NS = "http://mcd.rou.st.com/modules.php?name=mcu"
_NSMAP = {"mcu": _NS}

# Map CubeMX family/clock-tree identifiers to Zephyr DTS family directory names
FAMILY_DIR_MAP: dict[str, str] = {
    "STM32C0": "c0",
    "STM32F0": "f0",
    "STM32F1": "f1",
    "STM32F2": "f2",
    "STM32F3": "f3",
    "STM32F4": "f4",
    "STM32F7": "f7",
    "STM32G0": "g0",
    "STM32G4": "g4",
    "STM32H5": "h5",
    "STM32H7": "h7",
    "STM32H7RS": "h7rs",
    "STM32L0": "l0",
    "STM32L1": "l1",
    "STM32L4": "l4",
    "STM32L5": "l5",
    "STM32MP1": "mp1",
    "STM32MP13": "mp13",
    "STM32MP2": "mp2",
    "STM32N6": "n6",
    "STM32U0": "u0",
    "STM32U3": "u3",
    "STM32U5": "u5",
    "STM32WB": "wb",
    "STM32WB0": "wb0",
    "STM32WBA": "wba",
    "STM32WL": "wl",
}

# STM32 flash size letter → size in KB
FLASH_SIZE_MAP: dict[str, int] = {
    "4": 16, "6": 32, "8": 64,
    "B": 128, "C": 256, "D": 384, "E": 512,
    "F": 768, "G": 1024, "H": 1536, "I": 2048,
    "J": 2048, "K": 2048, "Z": 192,
}


@dataclass
class IpInfo:
    instance_name: str   # e.g., "USART2"
    name: str            # e.g., "USART"
    version: str
    config_file: Optional[str] = None
    clock_enable: Optional[str] = None


@dataclass
class PinSignal:
    name: str            # e.g., "USART2_TX"
    io_modes: Optional[str] = None


@dataclass
class PinInfo:
    name: str            # e.g., "PA2"
    position: str
    type: str            # "I/O", "Power", "Reset", etc.
    signals: list[PinSignal] = field(default_factory=list)


@dataclass
class McuInfo:
    ref_name: str        # e.g., "STM32L476R(C-E-G)Tx"
    family: str          # e.g., "STM32L4"
    line: str            # e.g., "STM32L4x6"
    clock_tree: str      # e.g., "STM32L4"
    package: str
    core: str
    freq_mhz: int
    ips: list[IpInfo] = field(default_factory=list)
    pins: list[PinInfo] = field(default_factory=list)

    @property
    def family_dir(self) -> Optional[str]:
        """Zephyr DTS family directory, e.g., 'l4'."""
        key = self.clock_tree or self.family
        # Try exact match, then prefix match
        if key in FAMILY_DIR_MAP:
            return FAMILY_DIR_MAP[key]
        for k, v in FAMILY_DIR_MAP.items():
            if key.startswith(k):
                return v
        return None

    def has_ip(self, instance_name: str) -> bool:
        return any(ip.instance_name == instance_name for ip in self.ips)

    def get_ip(self, instance_name: str) -> Optional[IpInfo]:
        for ip in self.ips:
            if ip.instance_name == instance_name:
                return ip
        return None

    def get_pin(self, pin_name: str) -> Optional[PinInfo]:
        for pin in self.pins:
            if pin.name == pin_name:
                return pin
        return None


def find_mcu_xml(mcu_name: str, mcu_dir: Path) -> Optional[Path]:
    """Find the XML file for a given MCU name in the CubeMX db/mcu/ directory.

    Matches against the MCU canonical name (e.g., 'STM32L476R(C-E-G)Tx').
    Falls back to glob-based search if exact match fails.
    """
    # Direct match
    exact = mcu_dir / f"{mcu_name}.xml"
    if exact.exists():
        return exact

    # The mcu_name from the IOC might be an exact variant like 'STM32L476RGTx'
    # while the DB file is 'STM32L476R(C-E-G)Tx.xml'. Try to find a match.
    name_upper = mcu_name.upper()
    for xml_file in mcu_dir.glob("STM32*.xml"):
        # Expand the pattern in the filename to see if it matches
        if _mcu_name_matches(xml_file.stem, mcu_name):
            return xml_file

    return None


def load_mcu(mcu_name: str, mcu_dir: Path) -> McuInfo:
    """Load MCU info from the CubeMX database.

    Args:
        mcu_name: MCU canonical name (Mcu.Name) or user name (Mcu.UserName).
        mcu_dir: Path to the CubeMX db/mcu/ directory.

    Raises:
        FileNotFoundError: If no matching XML is found.
    """
    xml_path = find_mcu_xml(mcu_name, mcu_dir)
    if xml_path is None:
        raise FileNotFoundError(
            f"No CubeMX MCU XML found for '{mcu_name}' in {mcu_dir}"
        )
    return _parse_mcu_xml(xml_path)


def _parse_mcu_xml(xml_path: Path) -> McuInfo:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    def tag(name: str) -> str:
        return f"{{{_NS}}}{name}"

    def find_text(elem, name: str) -> str:
        el = elem.find(tag(name))
        return el.text.strip() if el is not None and el.text else ""

    ref_name = root.attrib.get("RefName", xml_path.stem)
    family = root.attrib.get("Family", "")
    line = root.attrib.get("Line", "")
    clock_tree = root.attrib.get("ClockTree", family)
    package = root.attrib.get("Package", "")
    core = find_text(root, "Core")

    freq_str = find_text(root, "Frequency")
    try:
        freq_mhz = int(freq_str)
    except (ValueError, TypeError):
        freq_mhz = 0

    ips = []
    for ip_el in root.findall(tag("IP")):
        ips.append(IpInfo(
            instance_name=ip_el.attrib.get("InstanceName", ""),
            name=ip_el.attrib.get("Name", ""),
            version=ip_el.attrib.get("Version", ""),
            config_file=ip_el.attrib.get("ConfigFile"),
            clock_enable=ip_el.attrib.get("ClockEnableMode"),
        ))

    pins = []
    for pin_el in root.findall(tag("Pin")):
        pin_name = pin_el.attrib.get("Name", "")
        # Normalize: "PC14/OSC32_IN" → "PC14"
        pin_name = pin_name.split("/")[0]
        signals = []
        for sig_el in pin_el.findall(tag("Signal")):
            signals.append(PinSignal(
                name=sig_el.attrib.get("Name", ""),
                io_modes=sig_el.attrib.get("IOModes"),
            ))
        pins.append(PinInfo(
            name=pin_name,
            position=pin_el.attrib.get("Position", ""),
            type=pin_el.attrib.get("Type", ""),
            signals=signals,
        ))

    return McuInfo(
        ref_name=ref_name,
        family=family,
        line=line,
        clock_tree=clock_tree,
        package=package,
        core=core,
        freq_mhz=freq_mhz,
        ips=ips,
        pins=pins,
    )


def _mcu_name_matches(db_stem: str, query: str) -> bool:
    """Check if a DB filename stem matches the given MCU query name.

    e.g., db_stem='STM32L476R(C-E-G)Tx', query='STM32L476RGTx' → True
    """
    # Normalize case
    db_up = db_stem.upper()
    query_up = query.upper()

    if db_up == query_up:
        return True

    # Convert the DB pattern "(C-E-G)" into a regex character class
    # e.g., "STM32L476R(C-E-G)Tx" → "STM32L476R[CEG]Tx" (with dash ranges)
    pattern = re.sub(r"\(([^)]+)\)", lambda m: f"[{m.group(1).replace('-', '')}]", db_up)
    pattern = pattern.replace("X", ".")  # X is a wildcard in some patterns
    try:
        return bool(re.fullmatch(pattern, query_up))
    except re.error:
        return False
