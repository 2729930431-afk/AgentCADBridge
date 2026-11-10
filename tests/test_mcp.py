import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_real_stdio_handshake_and_discovery():
    async def run():
        root = Path(__file__).resolve().parents[1]
        params = StdioServerParameters(command=sys.executable, args=[str(root / "scripts" / "start_mcp.py")])
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            hello = await client.initialize()
            assert hello.serverInfo.name == "CAD"
            names = {t.name for t in (await client.list_tools()).tools}
            assert names == {
                "cad_connect",
                "cad_capabilities",
                "cad_catalog",
                "cad_documents",
                "cad_execute",
                "cad_batch",
                "cad_request_status",
                "cad_preview",
            }
            result = await client.call_tool("cad_documents", {"action": "new"})
            assert not result.structuredContent["ok"]

    asyncio.run(run())
