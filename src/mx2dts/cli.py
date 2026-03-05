"""mx2dts CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mx2dts",
        description="Convert STM32CubeMX .ioc files to Zephyr DTS",
    )
    parser.add_argument(
        "ioc_file",
        type=Path,
        help="Path to the .ioc file",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output .dts file (default: <ioc_stem>.dts in current directory)",
    )
    parser.add_argument(
        "--board-name",
        default=None,
        help="Board model name for the DTS (default: derived from MCU name)",
    )
    parser.add_argument(
        "--zephyr-base",
        type=Path,
        default=None,
        help="Path to Zephyr base directory (auto-detected if not given)",
    )
    parser.add_argument(
        "--hal-stm32",
        type=Path,
        default=None,
        help="Path to hal_stm32 dts/st/ directory (auto-detected if not given)",
    )
    parser.add_argument(
        "--cubemx-db",
        type=Path,
        default=None,
        help="Path to CubeMX db/ directory (auto-detected if not given)",
    )
    parser.add_argument(
        "--mode",
        choices=["board", "overlay"],
        default="board",
        help=(
            "Output mode: 'board' (default) generates a complete .dts file "
            "with root node and #include directives; 'overlay' generates a "
            "minimal .overlay suitable for adding to an existing Zephyr project."
        ),
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Exit 0 even if there are conversion warnings",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="mx2dts 0.1.0",
    )

    args = parser.parse_args(argv)

    # ── Import here to keep startup fast ─────────────────────────────────────
    from .paths import find_zephyr_paths, find_cubemx_db
    from .ioc_parser import parse_ioc
    from .mcu_db import load_mcu
    from .pinctrl_db import PinctrlDb
    from .context import ConversionContext
    from .dts_writer import generate_dts

    ioc_path = args.ioc_file
    if not ioc_path.exists():
        print(f"error: file not found: {ioc_path}", file=sys.stderr)
        return 1

    # ── Resolve paths ─────────────────────────────────────────────────────────
    print(f"Loading {ioc_path.name} …")
    ioc = parse_ioc(ioc_path)

    print(f"MCU: {ioc.mcu_user_name or ioc.mcu_name}")

    print("Locating Zephyr installation …")
    try:
        zephyr = find_zephyr_paths(
            zephyr_base=args.zephyr_base,
            hal_stm32=args.hal_stm32,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if zephyr is None:
        print(
            "error: Zephyr installation not found.\n"
            "Set ZEPHYR_BASE env var, or pass --zephyr-base / --hal-stm32.",
            file=sys.stderr,
        )
        return 1
    print(f"  Zephyr base : {zephyr.zephyr_base}")
    print(f"  hal_stm32   : {zephyr.hal_stm32_dts}")

    print("Locating CubeMX database …")
    try:
        cubemx = find_cubemx_db(args.cubemx_db)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if cubemx is None:
        print(
            "error: CubeMX database not found.\n"
            "Set CUBEMX_DB env var or pass --cubemx-db.",
            file=sys.stderr,
        )
        return 1
    print(f"  CubeMX DB   : {cubemx.db_root}")

    # ── Load MCU info ─────────────────────────────────────────────────────────
    mcu_name = ioc.mcu_name or ioc.mcu_user_name
    try:
        mcu = load_mcu(mcu_name, cubemx.mcu_dir)
    except FileNotFoundError:
        # Try user name
        try:
            mcu = load_mcu(ioc.mcu_user_name, cubemx.mcu_dir)
        except FileNotFoundError:
            print(
                f"error: MCU '{mcu_name}' not found in CubeMX database at {cubemx.mcu_dir}",
                file=sys.stderr,
            )
            return 1
    print(f"  MCU found   : {mcu.ref_name} ({mcu.family})")

    # ── Build context ─────────────────────────────────────────────────────────
    pinctrl_db = PinctrlDb(zephyr.hal_stm32_dts)
    ctx = ConversionContext(
        ioc=ioc,
        mcu=mcu,
        zephyr=zephyr,
        cubemx=cubemx,
        pinctrl_db=pinctrl_db,
    )

    # ── Generate DTS ──────────────────────────────────────────────────────────
    print(f"Converting ({args.mode} mode) …")
    dts_text = generate_dts(ctx, board_name=args.board_name, mode=args.mode)

    # ── Output ────────────────────────────────────────────────────────────────
    default_ext = ".overlay" if args.mode == "overlay" else ".dts"
    output_path = args.output or (ioc_path.stem + default_ext)
    output_path = Path(output_path)
    output_path.write_text(dts_text, encoding="utf-8")
    print(f"Written: {output_path}")

    # ── Report unhandled IOC items ────────────────────────────────────────────
    if ctx.unhandled_report:
        print(f"\n{len(ctx.unhandled_report)} IOC item(s) not rendered in DTS:")
        for item in ctx.unhandled_report:
            print(f"  {item}")

    # ── Report warnings ───────────────────────────────────────────────────────
    if ctx.warnings:
        print(f"\n{len(ctx.warnings)} warning(s):")
        for i, w in enumerate(ctx.warnings, 1):
            print(f"  [{i:02d}] {w}")
        if not args.warn_only:
            print(
                "\nReview warnings above. Pass --warn-only to suppress non-zero exit.",
                file=sys.stderr,
            )
            return 2
    else:
        print("No warnings — conversion complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
