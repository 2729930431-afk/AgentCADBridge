from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest
from PIL import Image, ImageChops

from cadbridge.backends.com import COMBackend
from cadbridge.core import Bridge
from cadbridge.preview import create_preview


class SnapshotBackend:
    """The preview service depends on this contract, with no CAD brand knowledge."""

    def __init__(self):
        self.calls = []

    def export_snapshot(self, document_id, path):
        self.calls.append(document_id)
        doc = ezdxf.new()
        space = doc.modelspace()
        space.add_lwpolyline([(0, 0), (10, 0), (10, 8), (0, 8)], close=True)
        space.add_circle((5, 4), 2, dxfattribs={"color": 1})
        space.add_text("PREVIEW", dxfattribs={"height": 0.6, "insert": (2, 3)})
        doc.saveas(path)
        return {"path": path, "context_unchanged": True}


def test_shared_preview_outputs_geometry_and_fixed_dimensions(tmp_path):
    backend = SnapshotBackend()
    bridge = Bridge(backend, lock=nullcontext, database=tmp_path / "audit.db")
    try:
        response = bridge.call(
            "preview",
            document_id="nonactive-doc",
            output_dir=str(tmp_path),
            width=640,
            height=480,
            theme="light",
        )
    finally:
        bridge.close()
    assert response["ok"], response
    result = response["result"]
    assert backend.calls == ["nonactive-doc"]
    assert result["entity_counts"] == {"LWPOLYLINE": 1, "CIRCLE": 1, "TEXT": 1}
    assert not result["uses_computer_control"]
    with Image.open(result["png"]) as image:
        assert image.size == (640, 480)
        white = Image.new("RGB", image.size, "white")
        assert ImageChops.difference(image.convert("RGB"), white).getbbox() is not None
    assert "<svg" in Path(result["svg"]).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "params", [{"width": 1}, {"height": 5000}, {"theme": "unknown"}, {"output_dir": "relative"}]
)
def test_invalid_preview_never_touches_cad(tmp_path, params):
    backend = SnapshotBackend()
    with pytest.raises(ValueError):
        create_preview(backend, "doc", **params)
    assert backend.calls == []


def test_failed_com_export_cleans_selection_without_ui_fallback(tmp_path):
    class Set:
        deleted = False

        def Delete(self):
            self.deleted = True

    selection = Set()

    def fail_export(*args):
        raise RuntimeError("not supported")

    doc = SimpleNamespace(
        Name="source.dwg",
        FullName="source.dwg",
        ModelSpace=SimpleNamespace(Count=3),
        GetVariable=lambda name: 0,
        SelectionSets=SimpleNamespace(Add=lambda name: selection),
        Export=fail_export,
    )
    backend = COMBackend()
    backend.bind = lambda document_id: doc
    backend.adapter = SimpleNamespace(cad_type="any-profile", application=SimpleNamespace(ActiveDocument=doc))
    with pytest.raises(RuntimeError, match="no UI fallback"):
        backend.export_snapshot("doc", str(tmp_path / "snapshot.dxf"))
    assert selection.deleted
