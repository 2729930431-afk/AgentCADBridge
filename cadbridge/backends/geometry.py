"""Vendor-independent array placement math used by the compatible COM backend."""

import math


def orbit(point, center, radians):
    dx, dy = point[0] - center[0], point[1] - center[1]
    return (
        center[0] + dx * math.cos(radians) - dy * math.sin(radians),
        center[1] + dx * math.sin(radians) + dy * math.cos(radians),
        point[2],
    )


def path_placements(points, count):
    """Return copy targets and rotations relative to the original first-segment direction."""
    if len(points) < 2 or count < 1:
        raise ValueError("Path needs at least two points and a positive item count")
    segments = []
    total = 0.0
    for a, b in zip(points, points[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length == 0:
            raise ValueError("Consecutive path points must differ")
        segments.append((a, b, total, length, math.atan2(b[1] - a[1], b[0] - a[0])))
        total += length
    result = []
    for i in range(1, count):
        distance = total * i / (count - 1)
        a, b, start, length, angle = next((s for s in segments if s[2] + s[3] >= distance), segments[-1])
        t = (distance - start) / length
        result.append(((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), 0.0), angle - segments[0][4]))
    return result
