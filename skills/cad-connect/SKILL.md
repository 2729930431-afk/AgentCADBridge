---
name: cad-connect
description: Connect to a running ZWCAD, AutoCAD, GstarCAD or BricsCAD through CADBridge, inspect documents and diagnose COM connection failures.
---

Use CADBridge's `cad_connect`, `cad_capabilities` and `cad_documents` tools. Default to ZWCAD and attach to the running instance; launch a new application only when requested or necessary for the user's task.

List documents and identify the intended drawing by name and full path. Retain its document_id. IDs belong to this MCP process and are invalid after reconnecting. Every drawing operation requires an explicit ID; activate that document using cad_documents if needed. New drawings use INSUNITS=4 (mm); existing drawings retain their units.

For a connection failure, check that CAD is open under the same Windows account and privilege level, finish modal dialogs/commands and retry the connection once. A missing COM registration requires repairing the CAD installation, not guessing another application's ProgID. This release has ZWCAD 2026 live validation; other profiles retain compatible COM configuration and need their own acceptance tests.

Tool discovery may require searching the available tools for `cad_` or `cad_bridge`. The installed Codex plugin display name is CAD; its technical name is cad.
