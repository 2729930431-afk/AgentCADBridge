"""Explicit live acceptance: creates its own test drawing; never edits the user's existing drawing."""

import asyncio
import json
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    output = root / ".runtime" / ("acceptance-" + uuid.uuid4().hex[:8] + ".dwg")
    checks = []
    params = StdioServerParameters(command=sys.executable, args=[str(root / "scripts" / "start_mcp.py")])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()

        async def call(name, **args):
            if name in ("cad_documents", "cad_execute", "cad_batch"):
                args.setdefault("request_id", str(uuid.uuid4()))
            result = await client.call_tool(name, args)
            data = result.structuredContent
            if not data or not data.get("ok"):
                raise AssertionError((name, data, result.content))
            return data["result"]

        connected = await call("cad_connect")
        original = next(d for d in connected["documents"] if d["active"])
        created = await call("cad_documents", action="new")
        doc_id = created["document_id"]
        owned = {doc_id}
        cleanup_errors = []
        try:
            checks.append("MCP stdio initialize/connect/new document")
            schema = await call("cad_catalog", operation="draw_line")
            assert "start" in schema["arguments_schema"]["properties"]
            checks.append("operation schema discovery")
            line_args = {
                "document_id": doc_id,
                "operation": "draw_line",
                "arguments": {"start": [0, 0], "end": [1000, 0]},
                "request_id": str(uuid.uuid4()),
            }
            handle = await call("cad_execute", **line_args)
            assert await call("cad_execute", **line_args) == handle
            count = await call("cad_execute", document_id=doc_id, operation="get_entity_counts", arguments={})
            assert sum(count.values()) == 1
            checks.append("entity creation/readback/idempotent replay")
            await call(
                "cad_execute",
                document_id=doc_id,
                operation="move_entities",
                arguments={"handles": [handle], "offset_x": 100, "offset_y": 200},
            )
            query = await call("cad_execute", document_id=doc_id, operation="query_entities", arguments={})
            assert query["entities"][0]["StartPoint"][:2] == [100, 200]
            checks.append("move and coordinate verification")
            await call(
                "cad_execute",
                document_id=doc_id,
                operation="set_entity_properties",
                arguments={"handle": handle, "properties": {"color": 1}},
            )
            prop = await call(
                "cad_execute",
                document_id=doc_id,
                operation="get_entity_properties",
                arguments={"handle": handle},
            )
            assert prop["color"] == 1
            checks.append("property edit/readback")
            await call("cad_execute", document_id=doc_id, operation="undo", arguments={})
            await asyncio.sleep(0.5)
            prop = await call(
                "cad_execute",
                document_id=doc_id,
                operation="get_entity_properties",
                arguments={"handle": handle},
            )
            assert prop["color"] != 1
            await call("cad_execute", document_id=doc_id, operation="redo", arguments={})
            await asyncio.sleep(0.5)
            prop = await call(
                "cad_execute",
                document_id=doc_id,
                operation="get_entity_properties",
                arguments={"handle": handle},
            )
            assert prop["color"] == 1
            checks.append("undo/redo with observed property changes")
            await call("cad_documents", action="activate", document_id=original["document_id"])
            rejected = await client.call_tool(
                "cad_execute",
                {
                    "document_id": doc_id,
                    "operation": "draw_circle",
                    "arguments": {"center": [0, 0], "radius": 100},
                    "request_id": str(uuid.uuid4()),
                },
            )
            assert not rejected.structuredContent["ok"]
            checks.append("document switch cannot redirect a write")
            await call("cad_documents", action="activate", document_id=doc_id)
            bad = await client.call_tool(
                "cad_batch",
                {
                    "document_id": doc_id,
                    "operations": [
                        {"operation": "draw_line", "arguments": {"start": [0, 0], "end": [1, 1]}},
                        {"operation": "draw_circle", "arguments": {"center": [0, 0], "radius": -1}},
                    ],
                    "request_id": str(uuid.uuid4()),
                },
            )
            assert not bad.structuredContent["ok"]
            count = await call("cad_execute", document_id=doc_id, operation="get_entity_counts", arguments={})
            assert sum(count.values()) == 1
            checks.append("batch validation prevents partial writes on invalid inputs")

            # Representative domain coverage; these additions stay in the test document.
            async def op(operation, **arguments):
                return await call("cad_execute", document_id=doc_id, operation=operation, arguments=arguments)

            await op("create_layer", name="QA-WALL", color=3)
            await op("set_entity_properties", handle=handle, properties={"layer": "QA-WALL"})
            assert "QA-WALL" in await op("list_layers")
            circle_handle = await op("draw_circle", center=[2000, 0], radius=250)
            await op("draw_ellipse", center=[3000, 0], major_axis_end=[500, 0], minor_axis_ratio=0.5)
            await op("draw_hatch", boundary_points=[[4000, 0], [4500, 0], [4500, 500], [4000, 500]])
            await op("add_dimension", start=[0, 0], end=[1000, 0], offset=500)
            await op(
                "draw_table",
                insertion_point=[0, 3000],
                num_rows=3,
                num_cols=2,
                row_height=200,
                col_width=500,
                title="QA",
                headers=["A", "B"],
                data=[["1", "2"]],
            )
            checks.append("layers/circle/ellipse/hatch/dimension/table")
            block = await op("create_block_from_entities", block_name="QA-BLOCK", entity_handles=[handle])
            assert block
            inserted = await op("insert_block", block_name="QA-BLOCK", insertion_point=[6000, 0])
            assert inserted
            assert "QA-BLOCK" in await op("list_blocks")
            copies = await op(
                "create_rectangular_array",
                handles=[handle],
                rows=2,
                columns=2,
                row_spacing=1000,
                column_spacing=1000,
            )
            assert len(copies) == 3
            await op("rotate_entities", handles=[handle], center_x=0, center_y=0, angle=30)
            await op("scale_entities", handles=[handle], center_x=0, center_y=0, scale_factor=2)
            checks.append("block definition/insertion and rectangular array/rotate/scale")
            polar = await op(
                "create_polar_array",
                handles=[circle_handle],
                center_x=0,
                center_y=0,
                count=3,
                rotate_items=False,
            )
            path = await op(
                "create_path_array",
                handles=[circle_handle],
                path_points=[[2000, 0], [3000, 0], [3000, 1000]],
                count=3,
                align_items=True,
            )
            entities = {item["handle"]: item for item in (await op("query_entities", limit=100))["entities"]}
            assert len(polar) == len(path) == 2
            assert round(entities[polar[0]]["Center"][0]) == -1000
            assert [round(v) for v in entities[path[-1]]["Center"][:2]] == [3000, 1000]
            checks.append("polar array without item rotation and path array with nonzero base")
            excel = output.with_suffix(".xlsx")
            await op("export_to_excel", filepath=str(excel))
            assert excel.is_file() and excel.stat().st_size > 0
            checks.append("Excel export to a new file")
            final = await call("cad_documents", action="inspect", document_id=doc_id)
            await call("cad_documents", action="save", document_id=doc_id, path=str(output))
            await call("cad_documents", action="close", document_id=doc_id, save_changes=True)
            owned.discard(doc_id)
            reopened = await call("cad_documents", action="open", path=str(output))
            owned.add(reopened["document_id"])
            assert reopened["modelspace_count"] == final["modelspace_count"]
            checks.append("save/close/reopen nonempty DWG")
        finally:
            for owned_id in owned:
                try:
                    await call("cad_documents", action="close", document_id=owned_id, save_changes=False)
                except Exception as error:
                    cleanup_errors.append(str(error))
            try:
                await call("cad_documents", action="activate", document_id=original["document_id"])
            except Exception as error:
                cleanup_errors.append(str(error))
        if cleanup_errors:
            raise RuntimeError({"cleanup_failed": cleanup_errors})
    report = {"ok": True, "cad": "ZWCAD 2026 Education", "checks": checks}
    (root / ".runtime" / "live-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
