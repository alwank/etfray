#!/usr/bin/env python3
"""Verify optional Performance chart dependencies."""

from etfray.domain.seasonals_plot import (
    chart_deps_status,
    chart_pixel_dimensions,
    chart_render_protocol,
    charts_available,
    terminal_cell_size,
)

if __name__ == "__main__":
    cell = terminal_cell_size()
    cols, rows, w, h = chart_pixel_dimensions(60, 28, cell_size=cell)
    print(chart_deps_status())
    print(f"charts_available: {charts_available()}")
    print(f"protocol: {chart_render_protocol()}")
    print(f"cell_size: {cell[0]}x{cell[1]} px")
    print(f"sample_render: {cols}x{rows} cells -> {w}x{h} px")
