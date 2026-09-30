# -*- coding: utf-8 -*-
"""AutoGUIWorld: GUI-agent training-data generation pipeline.

Exposes the repo-anchored data directory so storage / cost / dedup modules
resolve `data/` within the repository regardless of the working directory.
"""

import os

# The repository root is one level above this package.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, 'data')
