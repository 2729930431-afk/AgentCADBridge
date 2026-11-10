"""Codex-facing MCP is a thin adapter around the shared Bridge."""

import asyncio
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent
from pydantic import BaseModel, ConfigDict

from .core import Bridge

mcp = FastMCP(
    "CAD",
    instructions="CADBridge controls a local CAD. Connect, list documents, discover operation schemas, then execute against explicit document_id. Use a unique request_id per mutation; inspect partial or uncertain outcomes before retrying. Prefer cad_preview for background visual verification. When extending CADBridge, read the bundled cad-develop skill and preserve the upstream shared multi-CAD backend/profile architecture; isolate unsupported/vendor-only capabilities explicitly.",
)
bridge = Bridge()


async def invoke(method, **params):
    return await asyncio.wrap_future(bridge.submit(method, **params))


@mcp.tool()
async def cad_connect(
    cad_type: Literal["zwcad", "autocad", "gcad", "bricscad"] = "zwcad", launch: bool = False
) -> dict[str, Any]:
    """Attach to an open CAD via COM. launch=true explicitly allows starting CAD. Reconnecting invalidates old document IDs."""
    return await invoke("connect", cad_type=cad_type, launch=launch)


@mcp.tool(annotations={"readOnlyHint": True})
async def cad_capabilities() -> dict[str, Any]:
    """Inspect available profiles, implemented operations, execution guarantees and version limitations."""
    return await invoke("capabilities")


@mcp.tool(annotations={"readOnlyHint": True})
async def cad_catalog(operation: str = "") -> dict[str, Any]:
    """List operations by business domain; pass one operation to get its exact JSON arguments schema and description."""
    return await invoke("catalog", operation=operation)


@mcp.tool()
async def cad_documents(
    action: Literal["list", "new", "open", "activate", "inspect", "save", "close"],
    document_id: str = "",
    path: str = "",
    overwrite: bool = False,
    save_changes: bool = False,
    request_id: str = "",
) -> dict[str, Any]:
    """Manage explicit documents. New drawings use millimeters. Save uses an absolute DWG path; existing paths require overwrite=true. Close defaults to discarding unsaved changes: use only when requested. Use request_id for mutations."""
    if action not in ("list", "inspect") and not request_id.strip():
        return {"ok": False, "error": "Mutations require a nonempty unique request_id"}
    return await invoke(
        "documents",
        action=action,
        document_id=document_id,
        path=path,
        overwrite=overwrite,
        save_changes=save_changes,
        request_id=request_id,
    )


@mcp.tool()
async def cad_execute(document_id: str, operation: str, arguments: dict, request_id: str) -> dict[str, Any]:
    """Execute one catalog operation with validated named JSON arguments. Target document must be active; activate it explicitly. Always use a fresh request_id; reuse the same ID only to retrieve the same request's recorded result."""
    if not request_id.strip():
        return {"ok": False, "error": "request_id is required"}
    return await invoke(
        "execute", document_id=document_id, operation=operation, arguments=arguments, request_id=request_id
    )


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    arguments: dict


@mcp.tool()
async def cad_batch(document_id: str, operations: list[Operation], request_id: str) -> dict[str, Any]:
    """Prevalidate and execute 1..500 operations serially inside an undo group. Stops at first failure, reports completed items; no automatic rollback. Inspect result.complete and result.failure, even when envelope ok=true."""
    if not request_id.strip():
        return {"ok": False, "error": "request_id is required"}
    return await invoke(
        "batch",
        document_id=document_id,
        operations=[item.model_dump() for item in operations],
        request_id=request_id,
    )


@mcp.tool(annotations={"readOnlyHint": True})
async def cad_preview(
    document_id: str,
    output_dir: str = "",
    width: int = 1600,
    height: int = 1200,
    theme: Literal["dark", "light"] = "dark",
    layout_name: str = "Model",
) -> CallToolResult:
    """Render a document to PNG/SVG from a live DXF snapshot without window capture, activation or UI input.

    Uses the shared COM Export API for all CAD profiles, then a vendor-independent
    2D renderer. Includes unsaved drawing geometry. Fonts/proxy objects may differ
    from native CAD. Returns image content plus file paths and fidelity metadata.
    """
    import base64
    import json
    from pathlib import Path

    response = await invoke(
        "preview",
        document_id=document_id,
        output_dir=output_dir,
        width=width,
        height=height,
        theme=theme,
        layout_name=layout_name,
    )
    content = [TextContent(type="text", text=json.dumps(response, ensure_ascii=False))]
    if response["ok"]:
        png = Path(response["result"]["png"])
        content.append(
            ImageContent(
                type="image", mimeType="image/png", data=base64.b64encode(png.read_bytes()).decode("ascii")
            )
        )
    return CallToolResult(content=content, structuredContent=response, isError=not response["ok"])


@mcp.tool(annotations={"readOnlyHint": True})
async def cad_request_status(request_id: str) -> dict[str, Any]:
    """Read the durable execution record after a timeout; does not execute or repeat the request."""
    import json
    import sqlite3

    with sqlite3.connect(bridge.database) as db:
        try:
            row = db.execute(
                "SELECT method, started, result FROM requests WHERE id=?", (request_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
    if not row:
        return {"found": False}
    return {
        "found": True,
        "method": row[0],
        "started": row[1],
        "response": json.loads(row[2]) if row[2] else None,
        "outcome": "recorded" if row[2] else "running_or_unknown",
    }


def main():
    # Initialize native numerical/font libraries on the main thread, before COM
    # acquires STA proxies. Loading NumPy for the first time inside the COM worker
    # can stall its native DLL initialization on Windows.
    import ezdxf  # noqa: F401
    from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: F401

    try:
        mcp.run(transport="stdio")
    finally:
        bridge.close()
