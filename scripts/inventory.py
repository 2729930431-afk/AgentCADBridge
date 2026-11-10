"""Generate the public API/Skill inventory from source, without connecting to CAD."""

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect():
    tree = ast.parse((ROOT / "cadbridge/backends/com.py").read_text(encoding="utf-8"))
    groups = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GROUPS" for t in n.targets)
    )
    server = ast.parse((ROOT / "cadbridge/server.py").read_text(encoding="utf-8"))
    tools = [
        n.name
        for n in server.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and isinstance(d.func.value, ast.Name)
            and d.func.value.id == "mcp"
            and d.func.attr == "tool"
            for d in n.decorator_list
        )
    ]
    skills = [p.parent.name for p in sorted((ROOT / "skills").glob("*/SKILL.md"))]
    actions = ["list", "new", "open", "activate", "inspect", "save", "close"]
    return {
        "version": "0.1.0",
        "mcp_tool_count": len(tools),
        "mcp_tools": tools,
        "business_operation_count": sum(len(v.split()) for v in groups.values()),
        "business_operations": {k: v.split() for k, v in groups.items()},
        "document_action_count": len(actions),
        "document_actions": actions,
        "skill_count": len(skills),
        "skills": skills,
        "counting_note": "MCP entrypoints, catalog operations and document actions are separate layers; do not add them into a feature count.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "docs/inventory.json"
    result = collect()
    if args.check:
        if not target.is_file() or json.loads(target.read_text(encoding="utf-8")) != result:
            raise SystemExit("Inventory is stale; run python scripts/inventory.py")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "mcp_tool_count",
                    "business_operation_count",
                    "document_action_count",
                    "skill_count",
                )
            }
        )
    )
