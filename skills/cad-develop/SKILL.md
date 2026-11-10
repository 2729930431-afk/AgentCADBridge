---
name: cad-develop
description: Develop, extend, troubleshoot or maintain CADBridge and its Codex CAD plugin while preserving the upstream shared multi-CAD adapter architecture.
---

CADBridge extends AnCode666/multiCAD-mcp. Preserve its multi-CAD architecture in every new feature, fix, export, preview and future Agent adapter. ZWCAD is the initial live verification environment, not the architecture boundary.

Implement shared business behavior once. Keep Agent packages thin and keep Agent/CAD brand decisions out of the MCP and business core. AutoCAD, ZWCAD, GstarCAD and BricsCAD share the compatible COM backend with profile configuration; do not copy an implementation per product or add a ZWCAD-only shortcut in a general tool.

Use this extension sequence:

1. Inspect the existing operation registry, CADBackend contract and upstream adapter before adding an API.
2. Prefer a compatible COM operation in the shared backend. Separate host-independent processing, such as DXF rendering, into the shared service layer.
3. When a capability is absent or behaves differently, express it as a backend/profile capability with an explicit unsupported/error result. A genuinely vendor-specific API belongs in a dedicated backend/extension implementing the same contract. Explain the limitation; do not silently sacrifice the other CAD paths or declare untested compatibility.
4. Keep explicit document binding, schema validation, shared scheduling/locking, request records and partial-result semantics. Native backend code must not silently redirect writes to the active drawing.
5. Add meaningful shared-contract/fake-backend tests, then verify available CAD environments. Record separately what is implemented, what is unsupported and what was live-tested. Do not claim four-product validation from a ZWCAD-only run.
6. Update operation schemas, tools/skills inventory, documentation, dependency locks and installed plugin copies. The source repository must contain the complete runtime, upstream attribution and installation workflow.

For visual validation, prefer cad_preview and its shared background snapshot/render pipeline. Do not introduce screenshots, window focus or injected mouse/keyboard input as a hidden dependency of a general feature. Native CAD commands, when unavoidable, remain document-bound and require observable result verification.

Live tests are explicit opt-in scripts. Reuse one owned temporary drawing and close it in finally, including failure paths. Do not edit, save or close user drawings to make a test pass. Do not run a new-drawing demo during routine installation.

Keep vendor/multicad as the attributed upstream snapshot; put local compatibility changes in cadbridge/backends. After changes run the local checks described by the repository README. Never publish runtime logs, request databases or user drawings as test fixtures.
