# Keybindings

etfray is designed for keyboard-first navigation. Everything can be done without a mouse.

## Quick Reference

### Global

| Key | Action |
|-----|--------|
| `ctrl+p` | Open command palette |
| `ctrl+,` | Open settings |
| `ctrl+q` | Quit |
| `ctrl+s` | Save/export current view |

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

## Common Workflows

### Research an ETF

1. `ctrl+p` → type ticker (e.g., `VTI`) → `enter`
2. `tab` to move between Holdings, Exposure, Concentration views
3. `ctrl+s` to export the current view

### Compare two ETFs

1. `ctrl+p` → search first ETF → `enter`
2. Navigate to **Compare** view in the sidebar
3. Add a second ETF to the comparison

### Check your portfolio

1. Navigate sidebar: **Portfolio → Positions** (`down` / `enter`)
2. `tab` to switch between Positions, Lookthrough, Exposure, Margin views
3. `ctrl+s` to export any view

### Export data

1. Navigate to the view you want to export
2. `ctrl+s` → choose format (CSV or JSON)
3. File is saved to `~/.etfray/exports/`

### Change settings

1. `ctrl+,` to open Settings
2. Navigate to the setting you want to change
3. `escape` to return to your previous view

## Tips

- **`ctrl+p` is your best friend** — It's the fastest way to do anything. Search ETFs, switch views, run commands — all from the palette.
- **`tab` cycles panels** — Use it to move between the sidebar, main content, and detail panels without reaching for the mouse.
- **`escape` always goes back** — Dismiss dialogs, close the palette, or return to the previous view.
