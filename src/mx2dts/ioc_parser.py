"""Parse STM32CubeMX .ioc files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Signals that are handled as special cases (not regular pinctrl)
_SKIP_SIGNALS = frozenset({
    "SYS_JTMS-SWDIO", "SYS_JTCK-SWCLK", "SYS_JTDO-SWO",
    "SYS_JTDI", "SYS_JTRST", "SYS_TRACECLK", "SYS_TRACED0",
    "SYS_TRACED1", "SYS_TRACED2", "SYS_TRACED3",
})

_GPIO_SIGNALS = frozenset({"GPIO_Output", "GPIO_Input", "GPIO_Analog",
                             "GPIO_EVENTOUT", "GPIO_EXTI"})


@dataclass
class PinConfig:
    name: str                       # e.g., "PA2"
    signal: str                     # e.g., "USART2_TX"
    label: Optional[str] = None     # user-assigned GPIO_Label
    mode: Optional[str] = None      # e.g., "Asynchronous"
    pull: Optional[str] = None      # e.g., "GPIO_NOPULL"
    speed: Optional[str] = None     # e.g., "GPIO_SPEED_FREQ_LOW"
    gpio_mode: Optional[str] = None # e.g., "GPIO_MODE_AF_PP"
    locked: bool = False

    @property
    def is_gpio(self) -> bool:
        return self.signal in _GPIO_SIGNALS or self.signal.startswith("GPIO_")

    @property
    def is_skip(self) -> bool:
        return self.signal in _SKIP_SIGNALS or self.signal.startswith("SYS_")

    @property
    def peripheral(self) -> Optional[str]:
        """Extract peripheral name from signal, e.g., 'USART2' from 'USART2_TX'."""
        if self.is_gpio or self.is_skip:
            return None
        parts = self.signal.rsplit("_", 1)
        # Handle signals like RCC_OSC32_IN - skip
        if self.signal.startswith(("RCC_", "PWR_", "SYS_", "COMP_", "OPAMP_")):
            return None
        return parts[0] if len(parts) > 1 else None

    @property
    def pinctrl_label(self) -> Optional[str]:
        """Derive the expected Zephyr pinctrl label, e.g., 'usart2_tx_pa2'."""
        if self.is_gpio or self.is_skip or self.peripheral is None:
            return None
        pin_lower = self.name.lower()  # "pa2"
        signal_lower = self.signal.lower().replace("-", "_")  # "usart2_tx"
        return f"{signal_lower}_{pin_lower}"


@dataclass
class IocFile:
    path: Path
    raw: dict[str, str]

    # ── MCU identity ──────────────────────────────────────────────────────────

    @property
    def mcu_name(self) -> str:
        """Canonical MCU name, e.g., 'STM32L476R(C-E-G)Tx'."""
        return self.raw.get("Mcu.Name", "")

    @property
    def mcu_user_name(self) -> str:
        """Specific MCU variant, e.g., 'STM32L476RGTx'."""
        return self.raw.get("Mcu.UserName", "")

    @property
    def mcu_family(self) -> str:
        """Family string, e.g., 'STM32L4'."""
        return self.raw.get("Mcu.Family", "")

    @property
    def mcu_package(self) -> str:
        return self.raw.get("Mcu.Package", "")

    # ── Active IPs ────────────────────────────────────────────────────────────

    @property
    def active_ips(self) -> list[str]:
        """List of active IP instance names, e.g., ['RCC', 'USART2', 'SPI1']."""
        result = []
        i = 0
        while f"Mcu.IP{i}" in self.raw:
            result.append(self.raw[f"Mcu.IP{i}"])
            i += 1
        return result

    def has_ip(self, name: str) -> bool:
        return name in self.active_ips

    # ── Pin configuration ─────────────────────────────────────────────────────

    @property
    def _raw_pin_names(self) -> list[str]:
        names = []
        i = 0
        while f"Mcu.Pin{i}" in self.raw:
            names.append(self.raw[f"Mcu.Pin{i}"])
            i += 1
        return names

    @property
    def pins(self) -> dict[str, PinConfig]:
        """Dict of pin_name → PinConfig for all explicitly configured pins."""
        result: dict[str, PinConfig] = {}
        for raw_name in self._raw_pin_names:
            # Normalize: strip alternate function hint (e.g., "PC14/OSC32_IN" → "PC14")
            pin_name = raw_name.split("/")[0]

            # Skip virtual pins (VP_xxx) and power pins
            if pin_name.startswith(("VP_", "VBAT", "VDD", "VSS", "VCORE", "VREF")):
                continue

            signal = self.raw.get(f"{pin_name}.Signal", "")
            if not signal:
                continue

            result[pin_name] = PinConfig(
                name=pin_name,
                signal=signal,
                label=self.raw.get(f"{pin_name}.GPIO_Label"),
                mode=self.raw.get(f"{pin_name}.Mode"),
                pull=self.raw.get(f"{pin_name}.GPIO_PuPd"),
                speed=self.raw.get(f"{pin_name}.GPIO_Speed"),
                gpio_mode=self.raw.get(f"{pin_name}.GPIO_Mode"),
                locked=self.raw.get(f"{pin_name}.Locked", "").lower() == "true",
            )
        return result

    def pins_for_peripheral(self, peripheral: str) -> list[PinConfig]:
        """All pins assigned to a peripheral (e.g., 'USART2')."""
        return [p for p in self.pins.values() if p.peripheral == peripheral]

    def gpio_pins(self) -> list[PinConfig]:
        """All pins configured as plain GPIO."""
        return [p for p in self.pins.values() if p.is_gpio]

    # ── IP parameter access ───────────────────────────────────────────────────

    def get_ip_params(self, ip_name: str) -> dict[str, str]:
        """All IOC parameters for a given IP, with the IP prefix stripped."""
        prefix = f"{ip_name}."
        return {k[len(prefix):]: v for k, v in self.raw.items() if k.startswith(prefix)}

    def get_rcc(self) -> dict[str, str]:
        return self.get_ip_params("RCC")

    def get_nvic(self) -> dict[str, str]:
        return self.get_ip_params("NVIC")

    # ── DMA configuration ─────────────────────────────────────────────────────

    def get_dma_config(self) -> dict[str, list[dict[str, str]]]:
        """Return DMA config grouped by signal name.

        Structure: { "USART2_RX": [{"Channel": "DMA1_Channel6", ...}], ... }
        """
        pattern = re.compile(r"^Dma\.(\w+)\.(\d+)\.(\w+)$")
        raw_config: dict[str, dict[str, dict[str, str]]] = {}
        for key, value in self.raw.items():
            m = pattern.match(key)
            if m:
                signal, idx, param = m.groups()
                raw_config.setdefault(signal, {}).setdefault(idx, {})[param] = value

        return {
            signal: [entries[i] for i in sorted(entries)]
            for signal, entries in raw_config.items()
        }

    # ── Clock configuration helpers ───────────────────────────────────────────

    @property
    def sys_clock_freq_hz(self) -> Optional[int]:
        v = self.get_rcc().get("CortexFreq_Value") or self.get_rcc().get("SYSCLKFreq_VALUE")
        try:
            return int(float(v)) if v else None
        except (ValueError, TypeError):
            return None

    @property
    def ahb_freq_hz(self) -> Optional[int]:
        v = self.get_rcc().get("AHBFreq_Value") or self.get_rcc().get("HCLKFreq_Value")
        try:
            return int(float(v)) if v else None
        except (ValueError, TypeError):
            return None


def parse_ioc(path: Path) -> IocFile:
    """Parse a CubeMX .ioc file into an IocFile object."""
    raw: dict[str, str] = {}
    path = Path(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                # Unescape \: (CubeMX escapes colons in values like NVIC config)
                raw[key.strip()] = value.strip().replace("\\:", ":")
    return IocFile(path=path, raw=raw)
