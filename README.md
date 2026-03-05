# mx2dts

Convert [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html)
`.ioc` project files into [Zephyr RTOS](https://zephyrproject.org/) DeviceTree
Source (`.dts` / `.overlay`) files.

Instead of hand-writing DTS files from scratch, `mx2dts` reads your CubeMX
pin/peripheral configuration and generates a ready-to-review file with correct
node references, pinctrl bindings, clock settings, and flash partitions.

```bash
mx2dts my_board.ioc                        # → my_board.dts  (new board)
mx2dts my_board.ioc --mode overlay         # → my_board.overlay  (existing project)
```

---

## Features

- **20 peripheral converters** — clocks/RCC/PLL, GPIO (leds + keys),
  USART/UART/LPUART, SPI, I2C, ADC/DAC, DMA, Timers/PWM,
  CAN/FDCAN, USB OTG FS/HS, RTC, IWDG/WWDG, SDMMC, QUADSPI/OCTOSPI,
  Ethernet/RMII, RNG, CRC, SAI, I2S, DCMI
- **Real DMA request numbers** — looked up from CubeMX `db/mcu/IP/DMA-*.xml`
  or embedded tables compiled from ST reference manuals (F1, F4, L4, G4, H7,
  WB, WL, …). Config-cell flags (width, increment mode) are derived directly
  from IOC parameters.
- **Two output modes** — full `.dts` for a new board, or minimal `.overlay`
  for an existing Zephyr project
- **Path auto-detection** — finds Zephyr and CubeMX via west, env vars, or
  common install locations; works on Linux, macOS, and WSL

---

## Requirements

- Python 3.9+
- A Zephyr installation (for SoC/pinctrl DTSI files)
- STM32CubeMX installed, **or** just its `db/` directory

---

## Installation

```bash
pip install mx2dts
```

From source:

```bash
git clone https://github.com/yourname/mx2dts
cd mx2dts
pip install -e ".[dev]"
```

---

## Quick start

```bash
# Board mode (default) — generates a full .dts for a new board definition
mx2dts my_board.ioc

# Overlay mode — generates a .overlay to drop into an existing Zephyr app
mx2dts my_board.ioc --mode overlay -o app/boards/my_board.overlay

# Explicit paths (when auto-detection doesn't find the right installation)
mx2dts my_board.ioc \
    --zephyr-base ~/zephyrproject/zephyr \
    --hal-stm32   ~/zephyrproject/modules/hal/stm32/dts/st \
    --cubemx-db   ~/STM32CubeMX/db
```

---

## CLI reference

```
mx2dts <ioc_file> [options]

Positional:
  ioc_file                  Path to the CubeMX .ioc file

Options:
  -o, --output PATH         Output file (default: <stem>.dts or <stem>.overlay)
  --mode {board,overlay}    Output mode (default: board)
  --board-name NAME         Board model string (default: derived from MCU name)
  --zephyr-base PATH        Zephyr base directory
  --hal-stm32 PATH          hal_stm32 dts/st/ directory
  --cubemx-db PATH          CubeMX db/ directory
  --warn-only               Exit 0 even if there are conversion warnings
  --version                 Show version and exit
```

### Output modes

| Mode | Flag | Description |
|------|------|-------------|
| **Board** | `--mode board` *(default)* | Full `.dts`: `/dts-v1/;`, `#include` directives, root `/ { model; compatible; chosen; };`, flash partitions, all peripheral nodes. |
| **Overlay** | `--mode overlay` | Minimal `.overlay`: only `&peripheral { … };` stanzas — no version line, no root node. Drop straight into your Zephyr app's `boards/` directory. |

---

## Path auto-detection

`mx2dts` searches for Zephyr and CubeMX automatically so you rarely need
explicit `--` flags.

### Zephyr base

| Priority | Source |
|----------|--------|
| 1 | `--zephyr-base` CLI argument |
| 2 | `ZEPHYR_BASE` environment variable |
| 3 | `west list zephyr -f {abspath}` |
| 4 | `~/zephyrproject/zephyr`, `~/ncs/*/zephyr`, `/opt/zephyrproject/zephyr` |

### hal_stm32 (`dts/st/`)

| Priority | Source |
|----------|--------|
| 1 | `--hal-stm32` CLI argument |
| 2 | `HAL_STM32` env var (appends `/dts/st`) |
| 3 | `west list hal_stm32 -f {abspath}` |
| 4 | `<zephyr_base>/../modules/hal/stm32/dts/st` |
| 5 | `~/zephyrproject/modules/hal/stm32/dts/st` |

### CubeMX database (`db/`)

| Priority | Source |
|----------|--------|
| 1 | `--cubemx-db` CLI argument |
| 2 | `CUBEMX_DB` environment variable |
| 3 | `~/STM32CubeMX/db/` |
| 4 | `/opt/STM32CubeMX/db/`, `/opt/st/STM32CubeMX/db/` |
| 5 | WSL: `/mnt/c/Users/*/STM32CubeMX/db/` |

---

## DMA request numbers

For **pre-DMAMUX** families (F1, F2, F4, L1, L4, …) `mx2dts` looks up the
channel-selection register (CSELR) nibble from the CubeMX
`db/mcu/IP/DMA-<variant>.xml` file, falling back to embedded tables from ST
reference manuals.

For **DMAMUX** families (G0, G4, H7, WB, WL, L5, U5, …) the DMAMUX request
slot number is looked up the same way.

If the number cannot be determined, a warning is emitted and `0` is written as
a placeholder. The warning names the exact signal that needs verification.

---

## Warnings

Conversion warnings are printed to the console **and** embedded as a `/* … */`
block at the end of the generated file. Common causes:

| Warning | Action |
|---------|--------|
| Pinctrl label not found | Verify pin function is supported by this MCU variant |
| DMA request number unknown | Check ST reference manual for your MCU |
| SoC / pinctrl DTSI path not found | Pass `--zephyr-base` / `--hal-stm32` explicitly |
| CAN bus-speed not computed | APB1 clock frequency not found in IOC |

> **Always review the generated file before use in production.**

---

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Project layout

```
src/mx2dts/
├── cli.py           — argparse entry point
├── ioc_parser.py    — .ioc file parser  (IocFile, PinConfig)
├── mcu_db.py        — CubeMX MCU XML reader  (McuInfo)
├── pinctrl_db.py    — hal_stm32 pinctrl DTSI label indexer
├── dma_db.py        — DMA request number lookup (XML + embedded tables)
├── paths.py         — Zephyr + CubeMX path auto-detection
├── context.py       — ConversionContext (inputs + warning list)
├── dts_writer.py    — assembles final DTS / overlay text
└── converters/
    ├── clocks.py    serial.py   spi.py     i2c.py    adc.py
    ├── gpio.py      timers.py   dma.py     can.py    usb.py
    ├── rtc.py       watchdog.py sdmmc.py   qspi.py
    ├── ethernet.py  rng_crc.py  sai.py     i2s.py    dcmi.py
    └── __init__.py  — DtsNode, BaseConverter, ALL_CONVERTERS
```

---

## License

Apache-2.0
