"""Render one existing drawing through the real MCP transport; never creates a CAD document."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def render(name: str, output_dir: str):
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(command=sys.executable, args=[str(root / "scripts" / "start_mcp.py")])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        connection = await client.call_tool("cad_connect", {})
        data = connection.structuredContent
        if not data["ok"]:
            raise RuntimeError(data)
        doc = next((d for d in data["result"]["documents"] if d["name"] == name or d["path"] == name), None)
        if doc is None:
            raise ValueError(f"Requested drawing is not open: {name}; no document was opened or created")
        result = await client.call_tool(
            "cad_preview", {"document_id": doc["document_id"], "output_dir": output_dir}
        )
        data = result.structuredContent
        if not data["ok"]:
            raise RuntimeError(data)
        assert any(item.type == "image" and item.mimeType == "image/png" for item in result.content)
        assert data["result"]["export"]["context_unchanged"]
        print(json.dumps(data, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="existing document name or absolute path")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()
    asyncio.run(render(args.name, args.output_dir))
