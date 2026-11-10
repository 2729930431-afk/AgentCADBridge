"""A reproducible residential floor-plan sketch authored through the shared API."""

import uuid
from pathlib import Path


def floor_plan_operations():
    ops = []
    colors = {"A-WALL": 7, "A-DOOR": 30, "A-WIND": 4, "A-FURN": 8, "A-TEXT": 7, "A-DIMS": 2, "A-SHEET": 8}

    def add(operation, **arguments):
        ops.append({"operation": operation, "arguments": arguments})

    for layer, color in colors.items():
        add("create_layer", name=layer, color=color, lineweight=35 if layer == "A-WALL" else 13)
    add("set_text_style", name="CADBridge", font="msyh.ttc")

    def line(a, b, layer="A-WALL"):
        add("draw_line", start=a, end=b, layer=layer, color=colors[layer])

    def rect(x, y, w, h, layer="A-FURN"):
        add("draw_rectangle", corner1=[x, y], corner2=[x + w, y + h], layer=layer, color=colors[layer])

    def text(x, y, value, height=200, layer="A-TEXT", rotation=0):
        add(
            "draw_text",
            position=[x, y],
            text=value,
            height=height,
            layer=layer,
            color=colors[layer],
            rotation=rotation,
        )

    def circle(x, y, radius, layer="A-FURN"):
        add("draw_circle", center=[x, y], radius=radius, layer=layer, color=colors[layer])

    def horizontal(y, x1, x2, gaps=()):
        position = x1
        for a, b in sorted(gaps):
            if a > position:
                line([position, y], [a, y])
            position = b
        if position < x2:
            line([position, y], [x2, y])

    def vertical(x, y1, y2, gaps=()):
        position = y1
        for a, b in sorted(gaps):
            if a > position:
                line([x, position], [x, a])
            position = b
        if position < y2:
            line([x, position], [x, y2])

    # Exterior double-line walls with genuine door and window openings.
    for y in (0, 200):
        horizontal(y, 0, 12000, [(5500, 6500)])
    for y in (8800, 9000):
        horizontal(y, 0, 12000, [(1100, 2900), (5000, 7000), (9100, 10900)])
    for x in (0, 200):
        vertical(x, 0, 9000, [(1200, 3000), (5800, 7600)])
    for x in (11800, 12000):
        vertical(x, 0, 9000, [(1400, 2800), (6900, 8200)])
    for x in (3900, 4100):
        vertical(x, 200, 8800, [(1600, 2500), (5800, 6700)])
    for y in (4400, 4600):
        horizontal(y, 200, 3900)
    for x in (7900, 8100):
        vertical(x, 200, 8800, [(1600, 2500), (4300, 5100), (7000, 7900)])
    for y in (3500, 3700, 6100, 6300):
        horizontal(y, 8100, 11800)
    for y in (7500, 7650):
        horizontal(y, 4100, 7900, [(5300, 6800)])

    # Windows: three parallel glazing lines in the wall thickness.
    for a, b in [(1100, 2900), (5000, 7000), (9100, 10900)]:
        for y in (8830, 8900, 8970):
            line([a, y], [b, y], "A-WIND")
        for x in (a, b):
            line([x, 8800], [x, 9000], "A-WIND")
    for x0, spans in [(0, [(1200, 3000), (5800, 7600)]), (11800, [(1400, 2800), (6900, 8200)])]:
        for a, b in spans:
            for x in (x0 + 30, x0 + 100, x0 + 170):
                line([x, a], [x, b], "A-WIND")
            line([x0, a], [x0 + 200, a], "A-WIND")
            line([x0, b], [x0 + 200, b], "A-WIND")

    # Door leaves and swing arcs, including the entrance.
    for x, y, width, start, end in [
        (3900, 1600, 900, 90, 180),
        (3900, 5800, 900, 90, 180),
        (8100, 1600, 900, 0, 90),
        (8100, 4300, 800, 0, 90),
        (8100, 7000, 900, 0, 90),
        (5500, 200, 1000, 0, 90),
    ]:
        line([x, y], [x, y + width], "A-DOOR")
        add(
            "draw_arc",
            center=[x, y],
            radius=width,
            start_angle=start,
            end_angle=end,
            layer="A-DOOR",
            color=30,
        )
    line([5300, 7560], [6800, 7560], "A-WIND")
    line([5450, 7610], [6950, 7610], "A-WIND")

    # Bedroom furniture.
    for x, y in [(850, 5400), (850, 1050)]:
        rect(x, y, 1800, 2100)
        rect(x + 70, y + 1350, 1660, 650)
        rect(x + 100, y + 1570, 650, 350)
        rect(x + 950, y + 1570, 650, 350)
        rect(x - 450, y + 1400, 400, 500)
        rect(x + 1850, y + 1400, 400, 500)
    rect(260, 7850, 3300, 550)
    rect(260, 3500, 3300, 550)

    # Living / dining area, balcony, study.
    rect(4400, 3900, 850, 2400)
    for y in (4000, 4750, 5500):
        rect(4480, y, 680, 650)
    rect(5600, 4500, 1000, 1500)
    rect(7350, 4000, 350, 2500)
    rect(5700, 1400, 1400, 1700)
    for x in (5350, 7150):
        for y in (1550, 2400):
            rect(x, y, 300, 500)
    rect(4450, 7900, 750, 450)
    rect(6800, 7900, 750, 450)
    circle(6000, 8150, 300)
    rect(8500, 2600, 2700, 600)
    rect(9100, 2800, 850, 250)
    rect(9400, 2100, 550, 450)
    rect(8500, 650, 2500, 550)

    # Kitchen counters, hob, sink; bathroom fixtures.
    rect(8500, 8100, 2800, 600)
    rect(10700, 6600, 600, 1500)
    rect(8600, 8220, 900, 380)
    for x in (10100, 10550):
        circle(x, 8400, 120)
    rect(8500, 6500, 750, 1200)
    rect(10800, 3950, 800, 1800)
    line([10800, 3950], [11600, 5750], "A-FURN")
    rect(8500, 5300, 1300, 500)
    circle(9150, 5550, 170)
    rect(8700, 4000, 550, 750)
    circle(8975, 4350, 210)

    # Chinese room tags and secondary information.
    for x, y, label, area in [
        (1050, 8100, "主卧", "约 16.0 m2"),
        (1050, 3750, "次卧", "约 15.0 m2"),
        (5600, 6750, "客餐厅", "共享起居空间"),
        (9200, 7450, "厨房", "约 9.0 m2"),
        (9650, 4850, "卫生间", "干湿分区"),
        (9250, 1500, "书房", "可兼客卧"),
        (5550, 8500, "阳台", ""),
    ]:
        text(x, y, label, 240)
        if area:
            text(x, y - 310, area, 140)
    text(5540, 550, "入户", 170)

    # Dimension chains drawn explicitly so mm text size is independent of template DIMSTYLE.
    def dim_h(x1, x2, y, label):
        line([x1, y], [x2, y], "A-DIMS")
        for x in (x1, x2):
            line([x, y - 140], [x, y + 140], "A-DIMS")
            line([x - 70, y - 70], [x + 70, y + 70], "A-DIMS")
        text((x1 + x2) / 2 - len(label) * 45, y + 90, label, 170, "A-DIMS")

    for x in (0, 4000, 8000, 12000):
        line([x, 9100], [x, 10100], "A-DIMS")
    for x in (0, 4000, 8000):
        dim_h(x, x + 4000, 9550, "4000")
    dim_h(0, 12000, 10000, "12000")
    line([-650, 0], [-650, 9000], "A-DIMS")
    for y in (0, 9000):
        line([-800, y], [-450, y], "A-DIMS")
        line([-800, y], [0, y], "A-DIMS")
    text(-770, 4100, "9000", 170, "A-DIMS", 90)

    # Drawing frame, hierarchy, north marker and legend.
    rect(-1600, -1800, 15400, 13200, "A-SHEET")
    text(-1000, 10600, "CADBridge / 住宅建筑平面草图", 370)
    text(8050, 10630, "01   CONCEPT PLAN", 180, "A-DIMS")
    line([-1000, -700], [13000, -700], "A-SHEET")
    text(-1000, -1150, "两室一厅 + 书房   |   外轮廓 12.0 m × 9.0 m", 220)
    text(-1000, -1550, "单位：mm    概念示意，非施工图    |    CADBridge v0.1 / ZWCAD 2026", 160)
    text(9000, -1100, "WALL / DOOR / WINDOW", 160, "A-DIMS")
    text(9000, -1450, "2026.11  ·  A-01", 180)
    line([12900, 8000], [12900, 9200], "A-TEXT")
    line([12900, 9200], [12680, 8800], "A-TEXT")
    line([12900, 9200], [13120, 8800], "A-TEXT")
    text(12780, 9450, "N", 250)
    for a, b in [(0, 1000), (1000, 2000)]:
        line([a, -450], [b, -450], "A-DIMS")
        line([a, -500], [a, -400], "A-DIMS")
    text(0, -300, "0       1       2 m", 140, "A-DIMS")
    return ops


def create_demo(bridge, output=""):
    def call(method, **params):
        response = bridge.call(method, request_id=str(uuid.uuid4()), **params)
        if not response["ok"]:
            raise RuntimeError(response)
        return response["result"]

    doc = call("documents", action="new")
    document_id = doc["document_id"]
    result = call("batch", document_id=document_id, operations=floor_plan_operations())
    if not result["complete"]:
        return {"ok": False, "document": doc, "batch": result}
    call("execute", document_id=document_id, operation="refresh_view", arguments={})
    call("execute", document_id=document_id, operation="zoom_extents", arguments={})
    counts = call("execute", document_id=document_id, operation="get_entity_counts", arguments={})
    if not output:
        output = str(
            Path(__file__).resolve().parents[1]
            / "examples"
            / ("住宅平面草图-" + uuid.uuid4().hex[:6] + ".dwg")
        )
    saved = call("documents", action="save", document_id=document_id, path=str(Path(output).resolve()))
    return {"ok": True, "document": saved, "operations": len(result["completed"]), "entity_counts": counts}
