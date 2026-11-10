"""Stage a small host adapter with absolute runtime paths; never edit existing plugins."""

import json
import os
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
market = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CADBridge" / "codex-marketplace"
plugin = market / "plugins" / "cad"
plugin.mkdir(parents=True, exist_ok=True)
for name in (".codex-plugin", "skills", "assets"):
    shutil.copytree(root / name, plugin / name, dirs_exist_ok=True)
shutil.copy2(root / "plugin.json", plugin / "plugin.json")
server = {"command": str(Path(sys.executable).resolve()), "args": [str(root / "scripts" / "start_mcp.py")]}
for name in (".mcp.json", "mcp.json"):
    entry = dict(server)
    if name == "mcp.json":
        entry["type"] = "stdio"
    (plugin / name).write_text(
        json.dumps({"mcpServers": {"cad_bridge": entry}}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
catalog = {
    "name": "agent-cad-bridge-local",
    "interface": {"displayName": "CADBridge"},
    "plugins": [
        {
            "name": "cad",
            "source": {"source": "local", "path": "./plugins/cad"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        }
    ],
}
target = market / ".agents" / "plugins" / "marketplace.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Marketplace: {market}")
print(f"Runtime: {root}")
