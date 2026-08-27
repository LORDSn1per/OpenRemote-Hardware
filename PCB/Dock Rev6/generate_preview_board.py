#!/usr/bin/env python3
"""Compatibility entry point for the Dock Rev6 mechanical PCB generator."""

from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).resolve().with_name("generate_dock_rev6_mechanical_board.py")),
    run_name="__main__",
)
