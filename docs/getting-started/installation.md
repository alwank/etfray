# Installation

## Requirements

- Python 3.11 or later
- A terminal with 256-color support (most modern terminals)

## Install from PyPI

```bash
pip install etfray
```

## Optional: Seasonals chart support

For high-resolution matplotlib seasonals charts (instead of ASCII):

```bash
pip install etfray[charts]
```

This installs `matplotlib` and `textual-image` for inline terminal graphics.

**Terminal image support** is required for crisp charts. Supported terminals:

- iTerm2, Kitty, WezTerm (work out of the box)
- VS Code / Cursor: enable `terminal.integrated.enableImages` in settings, restart terminal
- Windows Terminal 1.22+

Without `[charts]` or without image support, etfray uses plotext ASCII charts automatically.

**Verify chart setup:**

```bash
python scripts/check_charts.py
```

See [Seasonals](../user-guide/seasonals.md) for details on chart modes and troubleshooting.

## Install from source

```bash
git clone https://github.com/alwank/etfray.git
cd etfray
pip install -e ".[dev]"
```

For charts support from source:

```bash
pip install -e ".[dev,charts]"
```

## Verify

```bash
etfray
```

This launches the TUI. Press `q` to quit.
