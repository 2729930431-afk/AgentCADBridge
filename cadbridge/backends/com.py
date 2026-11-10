"""Document-bound facade over the vendored multiCAD COM implementation.

Upstream is kept unmodified. Compatibility corrections belong in this facade.
"""

import inspect
import math
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Literal, get_type_hints

from pydantic import ConfigDict, create_model

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vendor" / "multicad" / "src"))

PROFILES = {
    "zwcad": "ZWCAD.Application",
    "autocad": "AutoCAD.Application",
    "gcad": "GCAD.Application",
    "bricscad": "BricscadApp.AcadApplication",
}

# An explicit registry prevents arbitrary COM member or Python execution.
GROUPS = {
    "drawing": "draw_line draw_circle draw_arc draw_rectangle draw_polyline draw_ellipse draw_text draw_hatch add_dimension draw_spline draw_leader draw_mleader draw_table",
    "entities": "get_entity_properties set_entity_properties delete_entity move_entities rotate_entities scale_entities change_entity_color change_entity_layer create_rectangular_array create_polar_array create_path_array",
    "layers": "create_layer set_current_layer get_current_layer list_layers get_layers_info rename_layer delete_layer turn_layer_on turn_layer_off is_layer_on set_layer_color set_entities_color_bylayer",
    "blocks": "create_block_from_entities insert_block list_blocks get_block_counts get_block_info get_block_references get_block_attributes set_block_attributes",
    "query": "select_by_color select_by_layer select_by_type get_entity_counts extract_drawing_data export_to_excel query_entities",
    "view": "zoom_extents refresh_view undo redo set_text_style",
}
READS = set(
    "get_entity_properties get_current_layer list_layers get_layers_info is_layer_on list_blocks get_block_counts get_block_info get_block_references get_block_attributes select_by_color select_by_layer select_by_type get_entity_counts extract_drawing_data query_entities".split()
)


class COMBackend:
    def __init__(self):
        self.adapter = None
        self.docs = {}
        self.models = {}
        self.batch_running = False
        self.groups = {op: group for group, words in GROUPS.items() for op in words.split()}

    def export_snapshot(self, document_id: str, path: str) -> dict:
        """Export DXF through the shared Automation API without activating a document.

        This is the same implementation for every configured CAD profile. No
        screenshot, SendCommand, SaveAs, document activation or window input.
        """
        doc = self.bind(document_id)
        target = Path(path)
        if not target.is_absolute() or target.suffix.lower() != ".dxf" or target.exists():
            raise ValueError("Snapshot requires a new absolute .dxf path")
        if int(doc.GetVariable("CMDACTIVE")):
            raise RuntimeError("Finish the active CAD command before requesting a snapshot")
        before = {
            "name": doc.Name,
            "path": doc.FullName,
            "entities": doc.ModelSpace.Count,
            "active_name": self.adapter.application.ActiveDocument.Name,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        selection = doc.SelectionSets.Add("CADBridgePreview_" + uuid.uuid4().hex[:12])
        try:
            # DXF ignores the selection contents; the API still requires this object.
            doc.Export(str(target.with_suffix("")), "DXF", selection)
        except Exception as error:
            raise RuntimeError(
                f"DXF snapshot failed for {self.adapter.cad_type}: {error}. "
                "This profile/version may not support background Document.Export; no UI fallback was used"
            ) from error
        finally:
            selection.Delete()  # Deletes the temporary set, never its drawing entities.
        if not target.is_file() or not target.stat().st_size:
            raise RuntimeError("Document.Export did not produce a nonempty DXF file")
        after = {
            "name": doc.Name,
            "path": doc.FullName,
            "entities": doc.ModelSpace.Count,
            "active_name": self.adapter.application.ActiveDocument.Name,
        }
        return {
            "path": str(target),
            "backend": "compatible-com",
            "cad_type": self.adapter.cad_type,
            "method": "Document.Export(DXF)",
            "before": before,
            "after": after,
            "context_unchanged": before == after,
        }

    def connect(self, cad_type: str = "zwcad", launch: bool = False) -> dict:
        import pythoncom
        import win32com.client
        from adapters.autocad_adapter import AutoCADAdapter

        if cad_type not in PROFILES:
            raise ValueError(f"Unknown CAD profile: {cad_type}; choose {list(PROFILES)}")
        # Initialization and all COM proxies live on the execution worker thread.
        pythoncom.CoInitialize()

        class PinnedAdapter(AutoCADAdapter):
            def create_polar_array(
                self,
                handles: list[str],
                center_x: float,
                center_y: float,
                count: int,
                angle_to_fill: float = 360.0,
                rotate_items: bool = True,
            ) -> list[str]:
                """Orbit copies around a center; rotate_items=false preserves each object's orientation."""
                from .geometry import orbit

                doc = self._get_document()
                center = (center_x, center_y, 0.0)
                copies = []
                step = angle_to_fill / (
                    count if math.isclose(abs(angle_to_fill), 360.0) else max(1, count - 1)
                )
                for handle in handles:
                    source = doc.HandleToObject(handle)
                    if not rotate_items:
                        low, high = source.GetBoundingBox()
                        anchor = tuple((low[i] + high[i]) / 2 for i in range(3))
                    for index in range(1, count):
                        angle = math.radians(step * index)
                        copy = source.Copy()
                        if rotate_items:
                            copy.Rotate(self._to_variant_array(center), angle)
                        else:
                            copy.Move(
                                self._to_variant_array(anchor),
                                self._to_variant_array(orbit(anchor, center, angle)),
                            )
                        copies.append(str(copy.Handle))
                return copies

            def create_path_array(
                self,
                handles: list[str],
                path_points: list[tuple[float, float]],
                count: int,
                align_items: bool = True,
            ) -> list[str]:
                """Copy a group along a 2D path. First path point is the original group base; preserve its offsets."""
                from .geometry import path_placements

                placements = path_placements(path_points, count)
                base = (*path_points[0], 0.0)
                doc = self._get_document()
                copies = []
                for handle in handles:
                    source = doc.HandleToObject(handle)
                    for target, angle in placements:
                        copy = source.Copy()
                        if align_items:
                            copy.Rotate(self._to_variant_array(base), angle)
                        copy.Move(self._to_variant_array(base), self._to_variant_array(target))
                        copies.append(str(copy.Handle))
                return copies

            def resolve_export_path(self, filename: str, folder_type: str = "drawings") -> str:
                if folder_type == "sheets" and getattr(self, "_excel_target", None):
                    return str(self._excel_target)
                return super().resolve_export_path(filename, folder_type)

            def export_to_excel(self, filepath: str = "drawing_data.xlsx") -> bool:
                """Export entities, layers and blocks to the exact new absolute XLSX path requested."""
                target = Path(filepath).expanduser().resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                self._excel_target = target
                try:
                    success = super().export_to_excel(str(target))
                    return bool(success and target.is_file() and target.stat().st_size)
                finally:
                    self._excel_target = None

            def draw_hatch(
                self,
                boundary_points: list[tuple[float, float] | tuple[float, float, float]],
                pattern: str = "SOLID",
                scale: float = 1.0,
                angle: float = 0.0,
                color: str | int = "white",
                layer: str = "0",
            ) -> str:
                """Create a planar hatch. Angle is degrees; preserve a hidden associative boundary."""
                doc = self._get_document()
                boundary = doc.ModelSpace.AddPolyline(
                    self._points_to_variant_array(
                        [tuple(p) if len(p) == 3 else (*p, 0.0) for p in boundary_points]
                    )
                )
                boundary.Closed = True
                boundary.Layer = layer
                hatch = doc.ModelSpace.AddHatch(0, pattern, True)
                hatch.AppendOuterLoop(self._objects_to_variant_array([boundary]))
                hatch.PatternScale = scale
                hatch.PatternAngle = math.radians(angle)
                hatch.Evaluate()
                boundary.Visible = False
                return self._finalize_entity(hatch, layer, color, entity_type="hatch", _skip_refresh=True)

            def draw_spline(
                self,
                points: list[tuple[float, float] | tuple[float, float, float]],
                closed: Literal[False] = False,
                degree: Literal[3] = 3,
                layer: str = "0",
                color: str | int = "white",
                lineweight: int = 0,
                _skip_refresh: bool = False,
            ) -> str:
                """Create an open cubic fit spline using the standard three-argument COM AddSpline API."""
                pts = [tuple(p) if len(p) == 3 else (*p, 0.0) for p in points]
                tangent1 = tuple(pts[1][i] - pts[0][i] for i in range(3))
                tangent2 = tuple(pts[-1][i] - pts[-2][i] for i in range(3))
                entity = self._get_document().ModelSpace.AddSpline(
                    self._points_to_variant_array(pts),
                    self._to_variant_array(tangent1),
                    self._to_variant_array(tangent2),
                )
                return self._finalize_entity(entity, layer, color, lineweight, "spline", _skip_refresh=True)

            def set_text_style(self, name: str = "CADBridge", font: str = "msyh.ttc") -> dict:
                doc = self._get_document()
                try:
                    style = doc.TextStyles.Item(name)
                except Exception:
                    style = doc.TextStyles.Add(name)
                style.FontFile = font
                doc.ActiveTextStyle = style
                return {"name": style.Name, "font": style.FontFile}

            def _validate_connection(self):
                if self.application is None:
                    raise RuntimeError("Call cad_connect first")
                _ = self.application.Name

            def _get_document(self, operation="operation"):
                self._validate_connection()
                if self.document is None:
                    raise RuntimeError("No document bound")
                if self.application.ActiveDocument._oleobj_ != self.document._oleobj_:
                    raise RuntimeError(
                        "Active document changed. Activate the bound document and inspect before retrying"
                    )
                return self.document

            def refresh_view(self):
                self._get_document().Regen(1)
                return True

            def _simulate_autocad_click(self):
                # UI input is never required by CADBridge's execution path.
                return False

            def undo(self, count: int = 1) -> dict:
                if not 1 <= count <= 100:
                    raise ValueError("count must be 1..100")
                self._get_document().SendCommand(f"_.UNDO\n{count}\n")
                return {"submitted": True, "verification_required": True}

            def redo(self, count: int = 1) -> dict:
                if count != 1:
                    raise ValueError("redo supports count=1")
                self._get_document().SendCommand("_.REDO\n")
                return {"submitted": True, "verification_required": True}

            def query_entities(
                self, offset: int = 0, limit: int = 100, layer: str = "", object_name: str = ""
            ) -> dict:
                if offset < 0 or not 1 <= limit <= 1000:
                    raise ValueError("offset >= 0 and limit 1..1000 required")
                space = self._get_document().ModelSpace
                found = []
                scanned = min(offset, space.Count)
                while scanned < space.Count and len(found) < limit:
                    entity = space.Item(scanned)
                    scanned += 1
                    if layer and entity.Layer != layer:
                        continue
                    if object_name and entity.ObjectName != object_name:
                        continue
                    item = self.get_entity_properties(str(entity.Handle))
                    for name in (
                        "TextString",
                        "InsertionPoint",
                        "StartPoint",
                        "EndPoint",
                        "Center",
                        "Radius",
                        "Coordinates",
                        "Area",
                        "Length",
                    ):
                        try:
                            value = getattr(entity, name)
                            item[name] = list(value) if isinstance(value, tuple) else value
                        except Exception:
                            pass
                    found.append(item)
                return {
                    "entities": found,
                    "next_offset": scanned if scanned < space.Count else None,
                    "modelspace_count": space.Count,
                }

        if self.adapter is not None:
            # Reconnecting deliberately invalidates process-local document IDs.
            self.adapter = None
            self.docs.clear()
        adapter = PinnedAdapter(cad_type)
        try:
            adapter.application = win32com.client.GetActiveObject(PROFILES[cad_type])
        except Exception:
            if not launch:
                raise RuntimeError(
                    f"No running {cad_type} COM instance. Open CAD, use the same Windows privilege level, then reconnect"
                ) from None
            adapter.application = win32com.client.Dispatch(PROFILES[cad_type])
            adapter.application.Visible = True
        self.adapter = adapter
        self._build_models()
        return {
            "cad_type": cad_type,
            "application": adapter.application.Name,
            "version": adapter.application.Version,
            "documents": self.documents("list"),
        }

    def _build_models(self):
        self.models.clear()
        for op in self.groups:
            method = getattr(self.adapter, op)
            hints = get_type_hints(method)
            fields = {}
            for name, param in inspect.signature(method).parameters.items():
                if name.startswith("_"):
                    continue
                fields[name] = (
                    hints.get(name, Any),
                    ... if param.default is inspect.Parameter.empty else param.default,
                )
            self.models[op] = create_model(
                op + "Arguments", __config__=ConfigDict(extra="forbid", allow_inf_nan=False), **fields
            )

    def catalog(self, operation: str = "") -> Any:
        if not self.adapter:
            raise RuntimeError("Call cad_connect before requesting operation schemas")
        if operation:
            if operation not in self.models:
                raise ValueError(f"Unknown operation {operation}")
            return {
                "operation": operation,
                "group": self.groups[operation],
                "read_only": operation in READS,
                "description": inspect.getdoc(getattr(self.adapter, operation)),
                "arguments_schema": self.models[operation].model_json_schema(),
            }
        return [
            {"operation": op, "group": group, "read_only": op in READS} for op, group in self.groups.items()
        ]

    def _remember(self, doc) -> dict:
        for key, existing in self.docs.items():
            if existing._oleobj_ == doc._oleobj_:
                return self._info(key, doc)
        key = str(uuid.uuid4())
        self.docs[key] = doc
        return self._info(key, doc)

    def _info(self, key, doc) -> dict:
        return {
            "document_id": key,
            "name": doc.Name,
            "path": doc.FullName,
            "saved": bool(doc.Saved),
            "active": doc._oleobj_ == self.adapter.application.ActiveDocument._oleobj_,
            "modelspace_count": doc.ModelSpace.Count,
            "insunits": doc.GetVariable("INSUNITS"),
        }

    def bind(self, document_id):
        if not self.adapter:
            raise RuntimeError("Call cad_connect first")
        if document_id not in self.docs:
            raise ValueError("Unknown document_id; list documents after reconnecting")
        doc = self.docs[document_id]
        # A stale COM proxy must never silently fall back to ActiveDocument.
        _ = doc.Name
        if not any(d._oleobj_ == doc._oleobj_ for d in self.adapter.application.Documents):
            raise ValueError("Document has been closed")
        self.adapter.document = doc
        return doc

    def documents(
        self,
        action: str,
        document_id: str = "",
        path: str = "",
        overwrite: bool = False,
        save_changes: bool = False,
    ) -> Any:
        if not self.adapter:
            raise RuntimeError("Call cad_connect first")
        app = self.adapter.application
        if (
            action not in ("list", "inspect")
            and app.Documents.Count
            and int(app.ActiveDocument.GetVariable("CMDACTIVE"))
        ):
            raise RuntimeError("CAD has an active command/dialog; finish it before changing documents")
        if action == "list":
            return [self._remember(d) for d in app.Documents]
        if action == "new":
            doc = app.Documents.Add()
            doc.SetVariable("INSUNITS", 4)
            return self._remember(doc)
        if action == "open":
            target = Path(path).expanduser()
            if (
                not target.is_absolute()
                or not target.is_file()
                or target.suffix.lower() not in (".dwg", ".dxf", ".dwt")
            ):
                raise ValueError("Provide an existing absolute DWG/DXF/DWT path")
            return self._remember(app.Documents.Open(str(target.resolve())))
        doc = self.bind(document_id)
        if action == "activate":
            doc.Activate()
            self._await_document_state(lambda: app.ActiveDocument._oleobj_ == doc._oleobj_)
        elif action == "inspect":
            pass
        elif action == "save":
            if path:
                target = Path(path).expanduser()
                if not target.is_absolute() or target.suffix.lower() != ".dwg":
                    raise ValueError(
                        "Save requires an absolute .dwg path; use data exports for other formats"
                    )
                if target.exists() and not overwrite:
                    raise FileExistsError(
                        "Target already exists; use a new path or explicitly set overwrite=true"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                doc.SaveAs(str(target.resolve()))
                if not target.is_file() or not target.stat().st_size:
                    raise RuntimeError("Save returned without a nonempty file")
            else:
                if not doc.Path:
                    raise ValueError("Unsaved drawing needs an absolute output path")
                doc.Save()
        elif action == "close":
            identity = doc._oleobj_
            doc.Close(save_changes)
            self._await_document_state(lambda: not any(d._oleobj_ == identity for d in app.Documents))
            del self.docs[document_id]
            return {"closed": document_id}
        else:
            raise ValueError("action must be list/new/open/activate/inspect/save/close")
        return self._info(document_id, doc)

    @staticmethod
    def _await_document_state(check):
        import pythoncom

        deadline = time.monotonic() + 5
        while not check():
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "CAD did not confirm the document transition; inspect state before retrying"
                )
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)

    def validate(self, operation: str, arguments: dict) -> dict:
        if operation not in self.models:
            raise ValueError(f"Unknown operation: {operation}")
        args = self.models[operation].model_validate(arguments).model_dump()
        if operation == "draw_line" and args["start"] == args["end"]:
            raise ValueError("Line endpoints must differ")
        if operation == "draw_rectangle" and (
            args["corner1"][0] == args["corner2"][0] or args["corner1"][1] == args["corner2"][1]
        ):
            raise ValueError("Rectangle must have nonzero width and height")
        if "points" in args and len(args["points"]) < (3 if args.get("closed") else 2):
            raise ValueError("Not enough points for the requested geometry")
        if "boundary_points" in args and len(args["boundary_points"]) < 3:
            raise ValueError("Hatch boundary requires at least 3 points")
        if operation == "draw_mleader" and (
            not args["leader_groups"] or any(len(g) < 2 for g in args["leader_groups"])
        ):
            raise ValueError("Each leader group requires at least 2 points")
        if operation == "draw_ellipse" and not 0 < args["minor_axis_ratio"] <= 1:
            raise ValueError("minor_axis_ratio must be in (0,1]")
        if "handles" in args and not args["handles"]:
            raise ValueError("handles cannot be empty")
        for name in ("rows", "columns", "num_rows", "num_cols", "count"):
            if name in args and not 1 <= args[name] <= 1000:
                raise ValueError(f"{name} must be 1..1000")
        if (
            operation == "create_rectangular_array"
            and args["rows"] * args["columns"] * len(args["handles"]) > 10000
        ):
            raise ValueError("Array exceeds 10000 objects; split the task")
        if operation == "create_block_from_entities" and not args["entity_handles"]:
            raise ValueError("entity_handles cannot be empty")
        if operation == "create_path_array":
            from .geometry import path_placements

            path_placements(args["path_points"], args["count"])
        if (
            operation in ("create_path_array", "create_polar_array")
            and args["count"] * len(args["handles"]) > 10000
        ):
            raise ValueError("Array exceeds 10000 objects; split the task")
        for name in ("radius", "height", "scale_factor", "major_radius", "minor_radius"):
            if name in args and args[name] <= 0:
                raise ValueError(f"{name} must be positive")
        if operation == "extract_drawing_data" and not (1 <= args["limit"] <= 1000 and args["offset"] >= 0):
            raise ValueError("limit 1..1000 and offset >= 0 required")
        if operation == "set_entity_properties" and set(args["properties"]) - {
            "layer",
            "color",
            "lineweight",
        }:
            raise ValueError("Supported properties: layer/color/lineweight")
        if operation == "export_to_excel":
            path = Path(args["filepath"]).expanduser()
            if not path.is_absolute() or path.suffix.lower() != ".xlsx" or path.exists():
                raise ValueError("Excel export requires a new absolute .xlsx path")
        return args

    def execute(self, document_id: str, operation: str, arguments: dict) -> Any:
        args = self.validate(operation, arguments)
        doc = self.bind(document_id)
        self.adapter._get_document(operation)
        if int(doc.GetVariable("CMDACTIVE")) != 0:
            raise RuntimeError("CAD has an active command; finish or cancel it before executing")
        method = getattr(self.adapter, operation)
        if "_skip_refresh" in inspect.signature(method).parameters:
            args["_skip_refresh"] = True
        undo_group = (
            operation not in READS
            and operation not in ("undo", "redo", "zoom_extents", "refresh_view", "export_to_excel")
            and not self.batch_running
        )
        if undo_group:
            doc.StartUndoMark()
        try:
            result = method(**args)
        finally:
            if undo_group:
                doc.EndUndoMark()
        if (
            result is False
            or result is None
            or (
                isinstance(result, dict)
                and (result.get("success") is False or result.get("status") == "error")
            )
        ):
            raise RuntimeError(f"{operation} reported failure; inspect state before retrying")
        if operation == "get_entity_properties" and not result:
            raise ValueError("Entity handle was not found in the bound document")
        if operation.startswith("draw_") or operation == "add_dimension":
            # Resolve every returned entity handle to verify creation.
            if isinstance(result, str):
                _ = doc.HandleToObject(result).ObjectName
        return result
