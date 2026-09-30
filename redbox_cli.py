# -*- coding: utf-8 -*-
"""Thin entrypoint for red-box extraction / stability report.

Usage:
    python redbox_cli.py [image_or_trajectory_directory]
"""

from autogui.analysis.redbox import main

if __name__ == '__main__':
    raise SystemExit(main())
