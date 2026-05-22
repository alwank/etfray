# Keybindings

etfray is designed for keyboard-first navigation. Everything can be done without a mouse.

## Quick Reference

### Global

| Key | Action |
|-----|--------|
| `ctrl+p` | Open command palette |
| `q` | Quit |
| `/` | Jump to ETF Search |
| `w` | Add current ETF to watchlist |
| `s` | Cycle data source (auto → edgar → web) |
| `ctrl+i` | Connect to IBKR |
| `escape` | Go back |

### View Shortcuts

| Key | Action |
|-----|--------|
| `p` | Portfolio overview |
| `t` | Seasonals |
| `h` | Holdings |
| `x` | Exposure |
| `c` | Concentration |
| `m` | Margin |
| `r` | Risk |
| `d` | Documents |

### Navigation

| Key | Action |
|-----|--------|
| `tab` | Move focus to next panel |
| `shift+tab` | Move focus to previous panel |
| `enter` | Select/activate item |
| `escape` | Go back / dismiss |

### Tables

| Key | Action |
|-----|--------|
| `up` / `down` | Navigate rows |
| `enter` | Select row |

### Sidebar

| Key | Action |
|-----|--------|
| `up` / `down` | Navigate tree |
| `enter` | Expand/collapse or navigate to view |

### Watchlist

| Key | Action |
|-----|--------|
| `a` | Focus the search/add input |
| `enter` | Open selected ETF |
| `delete` / `backspace` | Remove selected ETF |
| `ctrl+z` | Undo last removal |

## Common Workflows

### Research an ETF

1. `/` → type ticker (e.g., `VTI`) → `enter`
2. Use `h`, `x`, `c`, `r` to jump between Holdings, Exposure, Concentration, Risk
3. Press `t` to view Seasonals (year-over-year return chart)
4. Press `w` to add the ETF to your watchlist
5. Click the **Export** button (available in Holdings, Exposure, Concentration, Documents, and Compare views) to save to CSV

### View seasonals

1. `/` → search an ETF → `enter`
2. Press `t` to jump to Seasonals
3. Select year range to compare seasonal patterns
4. Review the period returns table below the chart

### Manage your watchlist

1. Navigate to **Workspace → Watchlist** in the sidebar
2. Press `a` to focus the search input, type a ticker, press Enter
3. Select a result and press Enter to add it
4. To remove: select a row and press `delete`
5. Press `ctrl+z` to undo a removal

### Compare two ETFs

1. `/` → search first ETF → `enter`
2. Navigate to **Compare** view in the sidebar
3. Add a second ETF to the comparison

### Check your portfolio

1. Press `p` to jump to Portfolio overview (or use sidebar)
3. Use `m` for Margin, `x` for Exposure, `c` for Concentration

### Export data

1. Navigate to a view with export support (Holdings, Exposure, Concentration, Documents, or Compare)
2. Click the **Export** button in the view
3. File is saved to `~/.etfray/exports/` (default location, configurable in Settings)

Alternatively, use **Workspace → Exports** for centralized export of holdings, positions, or margin data.

### Change settings

1. Navigate to **Workspace → Settings** in the sidebar, or use `ctrl+p` and type "Settings"
2. Edit the setting you want to change
3. `escape` to return to your previous view

## Tips

- **`/` for ETF search, `ctrl+p` for everything else** — Press `/` to jump straight to ETF Search. Use `ctrl+p` to open the command palette for navigation and commands.
- **Single-key shortcuts are fast** — Press `h` for holdings, `x` for exposure, `c` for concentration without any modifier keys.
- **`w` to watch** — Quickly build a watchlist as you research ETFs. Press `w` on any ETF to track it.
- **`escape` always goes back** — Dismiss dialogs, close the palette, or return to the previous view.
