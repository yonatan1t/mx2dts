# mx2dts

Convert [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` project files into [Zephyr RTOS](https://zephyrproject.org/) Device Tree Source (`.dts`) overlays.

Instead of hand-writing DTS files from scratch, mx2dts reads your CubeMX pin/peripheral configuration and generates a ready-to-review `.dts` file with the correct node references, pinctrl bindings, clock settings, and flash partitions.

## Features

- **Clocks** — system clock frequency from RCC configuration
- **GPIO** — gpio-leds and gpio-keys nodes from labeled pins
- **Serial (USART/LPUART)** — baud rate, parity, stop bits, pinctrl
- **SPI** — clock frequency, CPOL/CPHA, pinctrl
- **I2C** — clock frequency, pinctrl
- **ADC** — channel nodes with pinctrl
- **Timers** — PWM and counter nodes
- **DMA** — channel assignments emitted as annotated comments for manual verification
- Flash partition table with auto-detected flash size

## Requirements

- Python 3.9+
- A local [Zephyr](https://docs.zephyrproject.org/latest/develop/getting_started/index.html) installation (for SoC/pinctrl DTSI files)
- STM32CubeMX installed (for its MCU database), **or** the `db/` directory from a CubeMX installation

## Installation

```bash
pip install .
```

## Usage

```bash
mx2dts path/to/project.ioc
```

This writes `project.dts` in the current directory.

### Options

| Flag | Description |
|---|---|
| `-o FILE` | Output file path (default: `<stem>.dts`) |
| `--board-name NAME` | Board model string in the DTS (default: derived from MCU name) |
| `--zephyr-base PATH` | Path to Zephyr base (auto-detected via `ZEPHYR_BASE` env var) |
| `--hal-stm32 PATH` | Path to `hal_stm32/dts/st/` (auto-detected from Zephyr) |
| `--cubemx-db PATH` | Path to CubeMX `db/` directory (auto-detected or via `CUBEMX_DB` env var) |
| `--warn-only` | Exit 0 even when conversion warnings are present |
| `--version` | Print version and exit |

### Example

```bash
# Auto-detect Zephyr and CubeMX paths
mx2dts my_board.ioc -o boards/my_board.dts --board-name "My Custom Board"
```

## Output

The generated `.dts` file includes:

- SoC and pinctrl `#include` directives
- Root node with `model`, `compatible`, `chosen` (SRAM, flash, console)
- Flash partitions with a storage partition sized to the detected flash
- Overlay nodes for each active peripheral (`&usartX`, `&spiX`, `&i2cX`, etc.)
- DMA assignments as inline comments requiring manual review
- A warning block at the end listing anything that needs attention

> **Note:** Always review the generated file before using it in production. DMA request numbers and some clock settings may require manual verification.

## Auto-detection

mx2dts searches for Zephyr and CubeMX in common locations:

- `ZEPHYR_BASE` environment variable
- West workspace (`west topdir`)
- Default CubeMX install paths on Linux, macOS, and Windows
- `CUBEMX_DB` environment variable

## License

Apache-2.0
