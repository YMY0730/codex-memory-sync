#!/usr/bin/env python3
"""Codex Memory Sync GUI 入口"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import main
from src.config import ensure_config_dir

if __name__ == "__main__":
    ensure_config_dir()
    main()
