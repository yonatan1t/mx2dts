"""Streamlit web app for mx2dts — convert STM32CubeMX .ioc files to Zephyr DTS."""

from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="mx2dts — IOC → DTS Converter",
    page_icon="⚙️",
    layout="wide",
)

st.title("mx2dts — STM32CubeMX → Zephyr DTS Converter")
st.caption("Convert a `.ioc` project file into a Zephyr `.dts` board file or `.overlay`.")

# ── Sidebar: optional arguments ───────────────────────────────────────────────
with st.sidebar:
    st.header("Options")

    mode = st.radio(
        "Output mode",
        ["board", "overlay"],
        help=(
            "**board** — full `.dts` file with root node and `#include` directives.\n\n"
            "**overlay** — minimal `.overlay` to add to an existing Zephyr project."
        ),
    )

    board_name = st.text_input(
        "--board-name",
        value="",
        placeholder="Custom STM32XXX board",
        help="Board model name in the DTS (board mode only). Derived from MCU name if left empty.",
    )

    st.markdown("---")
    st.subheader("Path overrides")
    st.caption("Leave blank to auto-detect from environment / common install locations.")

    zephyr_base = st.text_input(
        "--zephyr-base",
        value="",
        placeholder="/home/user/zephyrproject/zephyr",
        help="Path to Zephyr base directory.",
    )
    hal_stm32 = st.text_input(
        "--hal-stm32",
        value="",
        placeholder="/home/user/zephyrproject/modules/hal/stm32/dts/st",
        help="Path to hal_stm32 `dts/st/` directory.",
    )
    cubemx_db = st.text_input(
        "--cubemx-db",
        value="",
        placeholder="/opt/STM32CubeMX/db",
        help="Path to CubeMX `db/` directory.",
    )

    st.markdown("---")
    warn_only = st.checkbox(
        "--warn-only",
        value=False,
        help="Treat conversion warnings as non-fatal (still shown in output).",
    )

# ── Main area: file upload + convert ─────────────────────────────────────────
uploaded = st.file_uploader("Upload your `.ioc` file", type=["ioc"])

if uploaded is None:
    st.info("Upload a CubeMX `.ioc` file to get started.")
    st.stop()

if st.button("Convert", type="primary"):
    with st.spinner("Converting…"):
        # Write uploaded file to a temp location so the parser gets a real Path
        with tempfile.NamedTemporaryFile(
            suffix=".ioc", delete=False, mode="wb"
        ) as tmp:
            tmp.write(uploaded.read())
            tmp_path = Path(tmp.name)

        try:
            from mx2dts.paths import find_zephyr_paths, find_cubemx_db
            from mx2dts.ioc_parser import parse_ioc
            from mx2dts.mcu_db import load_mcu
            from mx2dts.pinctrl_db import PinctrlDb
            from mx2dts.context import ConversionContext
            from mx2dts.dts_writer import generate_dts

            # Give the temp file the original name so the header comment looks right
            named_path = tmp_path.parent / uploaded.name
            tmp_path.rename(named_path)
            tmp_path = named_path

            # ── Parse IOC ────────────────────────────────────────────────────
            ioc = parse_ioc(tmp_path)
            mcu_label = ioc.mcu_user_name or ioc.mcu_name or "unknown MCU"
            st.write(f"**MCU detected:** `{mcu_label}`")

            # ── Resolve Zephyr paths ─────────────────────────────────────────
            zephyr = find_zephyr_paths(
                zephyr_base=Path(zephyr_base) if zephyr_base else None,
                hal_stm32=Path(hal_stm32) if hal_stm32 else None,
            )
            if zephyr is None:
                st.error(
                    "Zephyr installation not found. "
                    "Set the **--zephyr-base** and/or **--hal-stm32** paths in the sidebar, "
                    "or make sure `ZEPHYR_BASE` is set in the server environment."
                )
                st.stop()

            # ── Resolve CubeMX DB ────────────────────────────────────────────
            cubemx = find_cubemx_db(Path(cubemx_db) if cubemx_db else None)
            if cubemx is None:
                st.error(
                    "CubeMX database not found. "
                    "Set the **--cubemx-db** path in the sidebar, "
                    "or make sure `CUBEMX_DB` is set in the server environment."
                )
                st.stop()

            # ── Load MCU info ────────────────────────────────────────────────
            mcu_name = ioc.mcu_name or ioc.mcu_user_name
            try:
                mcu = load_mcu(mcu_name, cubemx.mcu_dir)
            except FileNotFoundError:
                try:
                    mcu = load_mcu(ioc.mcu_user_name, cubemx.mcu_dir)
                except FileNotFoundError:
                    st.error(
                        f"MCU `{mcu_name}` not found in CubeMX database at `{cubemx.mcu_dir}`. "
                        "Check your --cubemx-db path."
                    )
                    st.stop()

            # ── Convert ──────────────────────────────────────────────────────
            pinctrl_db = PinctrlDb(zephyr.hal_stm32_dts)
            ctx = ConversionContext(
                ioc=ioc,
                mcu=mcu,
                zephyr=zephyr,
                cubemx=cubemx,
                pinctrl_db=pinctrl_db,
            )
            dts_text = generate_dts(
                ctx,
                board_name=board_name or None,
                mode=mode,
            )

            # ── Warnings ─────────────────────────────────────────────────────
            if ctx.warnings:
                if warn_only:
                    st.warning(
                        f"{len(ctx.warnings)} conversion warning(s) — review the output."
                    )
                else:
                    st.warning(
                        f"{len(ctx.warnings)} conversion warning(s). "
                        "Enable **--warn-only** in the sidebar to suppress."
                    )
                with st.expander("Warnings", expanded=True):
                    for i, w in enumerate(ctx.warnings, 1):
                        st.write(f"`[{i:02d}]` {w}")
            else:
                st.success("Conversion complete — no warnings.")

            # ── Output ───────────────────────────────────────────────────────
            ext = ".overlay" if mode == "overlay" else ".dts"
            out_name = Path(uploaded.name).stem + ext

            st.download_button(
                label=f"Download `{out_name}`",
                data=dts_text,
                file_name=out_name,
                mime="text/plain",
            )

            st.code(dts_text, language="c", line_numbers=True)

        except Exception:
            st.error("Conversion failed with an unexpected error:")
            st.code(traceback.format_exc())
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
