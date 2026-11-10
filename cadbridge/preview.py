"""Host- and vendor-independent preview pipeline: snapshot DXF -> SVG/PNG.

Runs headlessly using Matplotlib's Agg canvas; there is no window capture path.
"""

import json
import uuid
from collections import Counter
from pathlib import Path

from .locking import state_dir


def render_snapshot(
    snapshot: Path, output: Path, width: int, height: int, theme: str, layout_name: str = "Model"
) -> dict:
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.properties import LayoutProperties
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from PIL import Image

    doc = ezdxf.readfile(snapshot)
    if layout_name not in doc.layouts:
        raise ValueError(f"Unknown layout {layout_name}; available: {doc.layout_names()}")
    drawing = doc.layouts.get(layout_name)
    context = RenderContext(doc)
    properties = LayoutProperties.from_layout(drawing)
    background = "#212830" if theme == "dark" else "#ffffff"
    properties.set_colors(background)
    figure = Figure(figsize=(width / 100, height / 100), dpi=100, facecolor=background)
    FigureCanvasAgg(figure)
    axes = figure.add_axes((0.025, 0.025, 0.95, 0.95))
    axes.set_axis_off()
    renderer = MatplotlibBackend(axes)
    skipped = []

    class ReportingFrontend(Frontend):
        def skip_entity(self, entity, reason=""):
            skipped.append({"handle": entity.dxf.handle, "type": entity.dxftype(), "reason": reason})
            super().skip_entity(entity, reason)

    frontend = ReportingFrontend(context, renderer, config=Configuration())
    frontend.draw_layout(drawing, finalize=True, layout_properties=properties)
    # ezdxf finalization fits the figure to geometry; restore the requested canvas.
    figure.set_size_inches(width / 100, height / 100, forward=True)
    axes.set_aspect("equal", adjustable="box")
    axes.margins(0.035)
    # Explicit paths and fixed canvas sizes, independent of any desktop viewport.
    png = output / "preview.png"
    svg = output / "preview.svg"
    figure.savefig(png, dpi=100, facecolor=background)
    figure.savefig(svg, facecolor=background)
    figure.clear()
    with Image.open(png) as image:
        if image.size != (width, height):
            raise RuntimeError("Preview dimensions failed verification")
        image.verify()
    counts = dict(Counter(e.dxftype() for e in drawing))
    return {
        "png": str(png),
        "svg": str(svg),
        "width": width,
        "height": height,
        "layout": layout_name,
        "entity_counts": counts,
        "skipped": skipped,
        "fidelity": "DXF geometry render; not the native CAD viewport or plot output",
        "limitations": [
            "2D preview; fonts, SHX, vendor proxy objects and external references may differ from CAD",
            "Skipped entries may include deliberately hidden entities/layers; inspect reasons",
        ],
    }


def create_preview(
    backend,
    document_id: str,
    output_dir: str = "",
    width: int = 1600,
    height: int = 1200,
    theme: str = "dark",
    layout_name: str = "Model",
) -> dict:
    if not 256 <= width <= 4096 or not 256 <= height <= 4096:
        raise ValueError("width and height must be 256..4096")
    if theme not in ("dark", "light"):
        raise ValueError("theme must be dark/light")
    if output_dir and not Path(output_dir).is_absolute():
        raise ValueError("output_dir must be absolute")
    base = Path(output_dir) if output_dir else state_dir() / "previews"
    output = base / uuid.uuid4().hex
    output.mkdir(parents=True)
    snapshot = output / "snapshot.dxf"
    exported = backend.export_snapshot(document_id, str(snapshot))
    rendered = render_snapshot(snapshot, output, width, height, theme, layout_name)
    result = {**rendered, "snapshot": str(snapshot), "export": exported, "uses_computer_control": False}
    (output / "metadata.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
