"""Plugin-local launcher: resolve the repository without depending on the shell cwd."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadbridge.server import main

main()
