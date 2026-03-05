"""Index pinctrl labels from hal_stm32 DTSI files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# Regex to extract pinctrl labels from DTSI files.
# Matches:  /omit-if-no-ref/ label_name: label_name {
_LABEL_RE = re.compile(
    r"/omit-if-no-ref/\s+(\w+)\s*:\s*\w+\s*\{[^}]*pinmux\s*=\s*<([^>]+)>",
    re.MULTILINE | re.DOTALL,
)

# Simplified: just extract all node labels (word: word {)
_NODE_LABEL_RE = re.compile(r"\b(\w+)\s*:\s*\w+\s*\{")


class PinctrlDb:
    """Index of all pinctrl labels available for a given MCU.

    Loads and caches the appropriate pinctrl DTSI file from hal_stm32.
    """

    def __init__(self, hal_stm32_dts: Path) -> None:
        """
        Args:
            hal_stm32_dts: Path to modules/hal/stm32/dts/st/
        """
        self._root = hal_stm32_dts
        self._cache: dict[str, dict[str, str]] = {}  # dtsi_path → {label: pinmux}

    def find_dtsi(self, mcu_name: str) -> Optional[Path]:
        """Find the pinctrl DTSI file for an MCU.

        Tries both the canonical name (e.g., 'STM32L476R(C-E-G)Tx') and the
        user variant name (e.g., 'STM32L476RGTx'), matching against filenames
        in the hal_stm32 dts/st/{family}/ directories.
        """
        stem = _mcu_name_to_dtsi_stem(mcu_name)
        family_dir = _mcu_name_to_family_dir(mcu_name)

        search_dirs = []
        if family_dir:
            search_dirs.append(self._root / family_dir)
        # Also search all family dirs as fallback
        search_dirs.extend(d for d in self._root.iterdir() if d.is_dir())

        for search_dir in search_dirs:
            # Try exact match
            candidate = search_dir / f"{stem}-pinctrl.dtsi"
            if candidate.exists():
                return candidate

            # Try to find by matching MCU name pattern
            for dtsi in search_dir.glob("*-pinctrl.dtsi"):
                if _dtsi_matches_mcu(dtsi.stem.replace("-pinctrl", ""), mcu_name):
                    return dtsi

        return None

    def get_labels(self, mcu_name: str) -> dict[str, str]:
        """Return all pinctrl labels for an MCU as {label: pinmux_spec}.

        Uses the matching DTSI file; returns empty dict if not found.
        """
        dtsi = self.find_dtsi(mcu_name)
        if dtsi is None:
            return {}
        key = str(dtsi)
        if key not in self._cache:
            self._cache[key] = _parse_pinctrl_dtsi(dtsi)
        return self._cache[key]

    def resolve_label(self, mcu_name: str, signal: str, pin: str) -> Optional[str]:
        """Return the Zephyr pinctrl label for a given signal on a given pin.

        Args:
            mcu_name: MCU canonical or user name.
            signal:   CubeMX signal name, e.g., 'USART2_TX'.
            pin:      Pin name, e.g., 'PA2'.

        Returns:
            Label string (e.g., 'usart2_tx_pa2') if found in the DTSI,
            or the derived label if the DTSI is unavailable.
        """
        candidate = _derive_label(signal, pin)
        if candidate is None:
            return None

        labels = self.get_labels(mcu_name)
        if not labels:
            # No DTSI found — return the derived label with a caveat
            return candidate

        return candidate if candidate in labels else None

    def dtsi_include_path(self, mcu_name: str) -> Optional[str]:
        """Return the DTS #include path for the pinctrl DTSI.

        e.g., 'st/l4/stm32l476r(c-e-g)tx-pinctrl.dtsi'
        """
        dtsi = self.find_dtsi(mcu_name)
        if dtsi is None:
            return None
        # Path relative to hal_stm32/dts/  (the include root)
        # dtsi is under hal_stm32/dts/st/{family}/{file}
        # Include path should be: st/{family}/{file}
        try:
            rel = dtsi.relative_to(self._root.parent)  # relative to dts/
            return str(rel).replace("\\", "/")
        except ValueError:
            return f"st/{dtsi.parent.name}/{dtsi.name}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _derive_label(signal: str, pin: str) -> Optional[str]:
    """Derive the expected pinctrl label from signal + pin names.

    Convention: '{signal_lower}_{pin_lower}', e.g., 'usart2_tx_pa2'.
    """
    if not signal or not pin:
        return None
    # Skip non-pinctrl signals
    if signal.startswith(("GPIO_", "SYS_", "RCC_", "PWR_", "COMP_")):
        return None
    signal_lower = signal.lower().replace("-", "_")
    pin_lower = pin.lower()
    return f"{signal_lower}_{pin_lower}"


def _mcu_name_to_dtsi_stem(mcu_name: str) -> str:
    """Convert MCU name to expected DTSI filename stem (without -pinctrl.dtsi).

    e.g., 'STM32L476R(C-E-G)Tx' → 'stm32l476r(c-e-g)tx'
         'STM32L476RGTx'         → 'stm32l476rgtx'  (but won't exist, need pattern)
    """
    return mcu_name.lower().replace(" ", "")


def _mcu_name_to_family_dir(mcu_name: str) -> Optional[str]:
    """Derive family directory from MCU name, e.g., 'STM32L476...' → 'l4'."""
    from .mcu_db import FAMILY_DIR_MAP
    name_up = mcu_name.upper()
    for family, dirname in FAMILY_DIR_MAP.items():
        if name_up.startswith(family):
            return dirname
    # Try series prefix (STM32L4xx → l4)
    m = re.match(r"STM32([A-Z]+\d+)", name_up)
    if m:
        series = m.group(1)  # e.g., "L476"
        sub = series[:2].lower()  # "l4"
        candidates = [d for d in FAMILY_DIR_MAP.values() if d.startswith(sub)]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _dtsi_matches_mcu(dtsi_stem: str, mcu_name: str) -> bool:
    """Check if a DTSI filename stem matches an MCU name.

    e.g., dtsi_stem='stm32l476r(c-e-g)tx', mcu_name='STM32L476RGTx' → True
    """
    stem_up = dtsi_stem.upper()
    query_up = mcu_name.upper()

    if stem_up == query_up:
        return True

    # Convert group patterns like (C-E-G) to regex
    pattern = re.sub(
        r"\(([^)]+)\)",
        lambda m: f"[{m.group(1).replace('-', '')}]",
        stem_up,
    )
    try:
        return bool(re.fullmatch(pattern, query_up))
    except re.error:
        return False


def _parse_pinctrl_dtsi(dtsi_path: Path) -> dict[str, str]:
    """Parse a pinctrl DTSI file and return {label: pinmux_spec}."""
    try:
        text = dtsi_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    labels: dict[str, str] = {}
    for m in _LABEL_RE.finditer(text):
        label = m.group(1)
        pinmux = m.group(2).strip()
        labels[label] = pinmux

    # Fallback: if the regex didn't capture pinmux details, at least collect labels
    if not labels:
        for m in _NODE_LABEL_RE.finditer(text):
            label = m.group(1)
            # Skip infrastructure labels
            if label not in ("soc", "pinctrl", "pin_controller"):
                labels[label] = ""

    return labels
