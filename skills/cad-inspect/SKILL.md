---
name: cad-inspect
description: Inspect and organize existing CAD drawings through CADBridge, including paginated entity queries, layers, blocks, object properties and Excel data export.
---

List documents, bind the requested drawing and inspect its units. Start with get_entity_counts, get_layers_info and list_blocks. Use query_entities with a bounded limit and follow next_offset; its offset counts ModelSpace positions, including filtered-out entities. Use handles for specific properties and block attributes. ModelSpace queries do not include every paper-space/layout object.

For bulk edits, first report or inspect the matched set, then use explicit handles and the requested properties. set_entity_properties supports layer, color and lineweight. An empty result from an inherited operation can also reflect a vendor compatibility issue; corroborate unexpected empty results with query_entities.

extract_drawing_data provides structured export data. export_to_excel requires a new absolute .xlsx path. This release does not expose plotting or professional mechanical BOM APIs. Use cad_capabilities to explain actual limits. Capability entries describe available implementation, not a promise that every vendor/version has been validated.

For errors and timeouts, use cad_request_status plus entity inspection before retrying. Closing a drawing defaults to save_changes=false, so close only when the user requested it and the requested save behavior is clear.

Use cad_preview for background visual inspection. It can preview a bound document while another drawing remains active, and returns a PNG image with DXF/SVG paths and render limitations. No window capture or computer control is needed. Its shared COM snapshot path is reused for every configured CAD profile; only ZWCAD 2026 has live preview verification so far.
