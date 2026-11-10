---
name: cad-draw
description: Create and edit CAD drawings with CADBridge, including geometry, text, dimensions, room plans, layers, blocks and entity transformations.
---

Connect and select an explicit document. Inspect INSUNITS and existing content. For a new drawing request, use cad_documents(action=new) and keep existing drawings open.

Use cad_catalog to discover operations; request the schema for unfamiliar operations. Submit named JSON arguments, not shorthand strings or CAD commands. Coordinates are WCS drawing units; arc/rotation angles use degrees where the returned schema/description specifies them. Query existing handles before modifying objects. Handles are scoped to the bound document.

For multi-entity work, use cad_batch with operation/arguments items. It prevalidates all inputs and uses one undo group, stops at the first failure, and returns completed items. Check result.complete and result.failure even when ok=true. It does not roll back earlier changes. Use a unique nonempty request_id per mutation. After a timeout, call cad_request_status and inspect entities; reusing an ID returns its recorded response and cannot perform a new operation.

Separate walls, doors, windows, furnishings, annotations and dimensions into layers. In a millimeter floor plan, choose readable text heights in the hundreds of units. set_text_style with msyh.ttc works for Chinese labels on the initial Windows/ZWCAD environment. The bundled demo uses real wall gaps, door arcs and three-line windows; it is a concept drawing, not a construction design.

For visual verification, use cad_preview(document_id). It exports a live DXF snapshot through the shared multi-CAD COM backend and returns a PNG image, SVG file and metadata. It requires no computer control, document activation, viewport changes or screenshots. It includes unsaved geometry; it is a 2D DXF render, so native fonts, proxy objects and external references may differ. Inspect skipped entities and fidelity metadata when these matter. Use this background preview before considering window capture. Save to a new absolute DWG path requested or appropriate for the task. Existing output paths require explicit overwrite=true. Do not claim success from submitted undo/redo commands until queried state confirms the change.
