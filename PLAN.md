# mx2dts — Project Plan

## Goal

Convert STM32CubeMX `.ioc` project files into Zephyr RTOS DeviceTree Source
(`.dts` or `.overlay`) files, using the CubeMX MCU database and the Zephyr
source tree as reference data. The conversion should be as faithful as possible
to what is expressed in the `.ioc` file.

---

## Output Modes

| Mode | Flag | Description |
|------|------|-------------|
| Board DTS | `--mode board` *(default)* | Full `.dts` for a new board: `/dts-v1/;`, SoC & pinctrl `#include`s, root node (`model`, `compatible`, `chosen`), flash partitions, all peripheral nodes. |
| Overlay | `--mode overlay` | Minimal `.overlay` for an existing Zephyr project: only `&node { ... };` stanzas, no `/dts-v1/;`, no root node, no includes. |

---

## CLI Interface

```
mx2dts <ioc_file> [options]

Arguments:
  ioc_file                  Path to the .ioc file

Options:
  -o, --output PATH         Output file (default: <stem>.dts or <stem>.overlay)
  --mode {board,overlay}    Output mode (default: board)
  --board-name NAME         Board model name (default: derived from MCU)
  --zephyr-base PATH        Zephyr base directory (auto-detected if omitted)
  --hal-stm32 PATH          hal_stm32 dts/st/ directory (auto-detected if omitted)
  --cubemx-db PATH          CubeMX db/ directory (auto-detected if omitted)
  --warn-only               Exit 0 even if there are conversion warnings
  --version                 Show version
```

---

## Path Auto-Detection Order

**Zephyr base:**
1. `--zephyr-base` CLI arg
2. `ZEPHYR_BASE` env var
3. `west list zephyr -f {abspath}`
4. `~/zephyrproject/zephyr`, `~/ncs/*/zephyr`, `/opt/zephyrproject/zephyr`

**hal_stm32 (`dts/st/`):**
1. `--hal-stm32` CLI arg
2. `HAL_STM32` env var (appends `/dts/st`)
3. `west list hal_stm32 -f {abspath}`
4. Relative to zephyr_base: `../modules/hal/stm32/dts/st`
5. `~/zephyrproject/modules/hal/stm32/dts/st`, `~/ncs/*/modules/hal/stm32/dts/st`

**CubeMX database (`db/`):**
1. `--cubemx-db` CLI arg
2. `CUBEMX_DB` env var
3. `~/STM32CubeMX/db/`
4. `/opt/STM32CubeMX/db/`, `/opt/st/STM32CubeMX/db/`
5. WSL: `/mnt/c/Users/*/STM32CubeMX/db/`, `/mnt/c/Users/*/AppData/Local/STM32CubeMX/db/`

---

## Implementation Status

### ✅ Completed

- [x] IOC file parser — `ioc_parser.py`
- [x] CubeMX MCU XML reader — `mcu_db.py`
- [x] Pinctrl DTSI label indexer — `pinctrl_db.py`
- [x] Zephyr + CubeMX path auto-detection — `paths.py`
- [x] Conversion context with warning tracking — `context.py`
- [x] DTS file assembler — `dts_writer.py`
- [x] CLI entry point with all path args — `cli.py`
- [x] `--mode board` output (full DTS with root node, includes, flash partitions)
- [x] Converters:
  - [x] Clocks / RCC / PLL / oscillators (`converters/clocks.py`)
  - [x] GPIO → `gpio-leds` / `gpio-keys` nodes (`converters/gpio.py`)
  - [x] USART / UART / LPUART (`converters/serial.py`)
  - [x] SPI (`converters/spi.py`)
  - [x] I2C / FMPI2C (`converters/i2c.py`)
  - [x] ADC / DAC (`converters/adc.py`)
  - [x] DMA — channel/direction/priority extracted; request number is **placeholder `0`** (`converters/dma.py`)
  - [x] Timers / PWM (`converters/timers.py`)
- [x] Tests: IOC parser (`tests/test_ioc_parser.py`)

---

### 🔲 To Do

#### P1 — Core correctness

- [ ] **DMA request numbers** — look up real values from CubeMX IP XML files.
  - Location: `db/mcu/IP/DMA-<variant>.xml` and `DMAMUX-<variant>.xml`
  - Pre-DMAMUX MCUs (F1, F2, F4, L1, L4, …): fixed channel→request mapping
    defined in the DMA IP XML.
  - DMAMUX MCUs (G0, G4, H7, L5, U5, WB, …): request slot numbers defined
    in the DMAMUX IP XML; any channel can carry any request.
  - Emit correct Zephyr DMA cell: `<&dmaX channel request flags>`.
  - Remove the current placeholder warning once real values are emitted.

- [ ] **`--mode overlay`** — implement overlay output mode.
  - Skip `/dts-v1/;`, `#include` lines, root node, and flash partitions.
  - Emit only `&peripheral { ... };` stanzas.
  - Default output file extension: `.overlay`.
  - Wire up in `cli.py` and `dts_writer.py`.

#### P2 — Additional peripheral converters

Add a converter for each peripheral that Zephyr supports on STM32.
Each converter should extract all relevant `.ioc` parameters (mode, speed,
prescaler, etc.) and emit the correct Zephyr DTS properties and pinctrl refs.

| Peripheral | Zephyr node | Key properties |
|---|---|---|
| USB OTG FS / HS | `&usbotg_fs`, `&usbotg_hs` | `pinctrl-0`, `status` |
| CAN / FDCAN | `&can1`, `&fdcan1` | `bus-speed`, `sample-point`, `pinctrl-0` |
| RTC | `&rtc` | `clocks`, `prescaler` |
| IWDG | `&iwdg` | `status` (config is minimal in DTS) |
| WWDG | `&wwdg` | `status` |
| SDMMC | `&sdmmc1`, `&sdmmc2` | `bus-width`, `clk-div`, `pinctrl-0` |
| QUADSPI | `&quadspi` | `clock-prescaler`, `pinctrl-0` |
| OCTOSPI | `&octospi1`, `&octospi2` | `clock-prescaler`, `pinctrl-0` |
| Ethernet / RMII | `&mac` | `pinctrl-0`, `phy-connection-type` |
| RNG | `&rng` | `status` only |
| CRC | `&crc` | `status` only |
| SAI | `&sai1`, `&sai2` | `pinctrl-0`, `mclk-division`, audio format |
| I2S | `&i2s2`, `&i2s3` | `pinctrl-0`, `frame-format` |
| DCMI | `&dcmi` | `pinctrl-0` |
| FDMA / MDMA | `&mdma1` | similar to DMA |

#### P3 — Tests

- [ ] Unit tests for each converter (serial, spi, i2c, adc, gpio, timers, clocks, dma)
- [ ] Unit tests for DTS writer: board mode vs overlay mode
- [ ] Unit tests for DMA request number lookup
- [ ] Integration test: parse a real `.ioc` → run full pipeline → validate DTS structure
  *(real `.ioc` file to be provided)*

#### P4 — Polish

- [ ] `README.md` — usage examples, auto-detection notes, contribution guide
- [ ] `pyproject.toml` — add classifiers, `[project.urls]`, long description
- [ ] Optional: validate generated DTS with Zephyr `dt-validate`
  (requires `devicetree` extra: `pip install mx2dts[zephyr]`)
