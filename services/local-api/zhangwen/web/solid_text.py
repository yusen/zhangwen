"""Bounded text solids from the bundled CJK font, no OS fonts or model code."""
from typing import Literal
import math

from pydantic import Field, model_validator
from .design_specs import Strict
from .laser_text import outlines


class TextOperation(Strict):
    kind: Literal['text'] = 'text'
    operation: Literal['add', 'cut'] = 'cut'
    text: str = Field(min_length=1, max_length=20)
    fontSize: float = Field(ge=2, le=80)
    depth: float = Field(ge=.1, le=10)
    center: list[float] = Field(min_length=3, max_length=3)
    face: Literal['top', 'bottom', 'front', 'back', 'left', 'right']
    angle: float = Field(default=0, ge=-360, le=360)

    @model_validator(mode='after')
    def bounded(self):
        if any(not math.isfinite(n) or abs(n) > 1000 for n in self.center):
            raise ValueError('文字位置超出范围。')
        width, _ = outlines(self.text, self.fontSize)
        if width > 300:
            raise ValueError('文字宽度不能超过300毫米。')
        return self


# Seen from outside the chosen face: X right, Y up. Bottom is not mirrored.
FRAMES = {'top': ((1, 0, 0), (0, 0, 1)), 'bottom': ((1, 0, 0), (0, 0, -1)),
          'front': ((1, 0, 0), (0, -1, 0)), 'back': ((-1, 0, 0), (0, 1, 0)),
          'left': ((0, -1, 0), (-1, 0, 0)), 'right': ((0, 1, 0), (1, 0, 0))}


def piece(operation):
    import cadquery as cq
    op = TextOperation.model_validate(operation)
    width, contours = outlines(op.text, op.fontSize)
    xdir, normal = FRAMES[op.face]
    # Overlap the external face by 0.02mm to avoid coincident booleans, while
    # retaining the exact nominal cut depth / relief height.
    normal = cq.Vector(normal)
    origin = cq.Vector(op.center) + normal * (.02 if op.operation == 'cut' else -.02)
    plane = cq.Plane(origin, xDir=xdir, normal=normal).rotated((0, 0, op.angle))
    wires = [cq.Wire.makePolygon([plane.toWorldCoords((x-width/2, op.fontSize/2-y)) for x, y in contour], close=True)
             for contour in contours]
    areas = [sum(x * path[(j+1) % len(path)][1] - path[(j+1) % len(path)][0] * y
                 for j, (x, y) in enumerate(path)) / 2 for path in contours]
    # The bundled font uses clockwise outer ink in Y-down coordinates. Group
    # each counter with its containing stroke, not with the first wire: a CJK
    # glyph contains many disconnected strokes and some same-winding overlaps.
    def contains(path, point):
        x, y = point; inside = False
        for a, b in zip(path, path[1:] + path[:1]):
            if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0]) * (y-a[1]) / (b[1]-a[1]) + a[0]:
                inside = not inside
        return inside
    outer = [i for i, area in enumerate(areas) if area > 0]
    holes = {i: [] for i in outer}
    for i, area in enumerate(areas):
        if area >= 0:
            continue
        parents = [j for j in outer if contains(contours[j], contours[i][0])]
        if not parents:
            raise ValueError('文字内部轮廓没有对应外轮廓。')
        holes[min(parents, key=lambda j: areas[j])].append(wires[i])
    distance = -(op.depth + .02) if op.operation == 'cut' else op.depth + .02
    solids = [cq.Solid.extrudeLinear(wires[i], holes[i], plane.zDir.multiply(distance)) for i in outer]
    result = cq.Workplane(plane).newObject(solids).combine().clean()
    if not result.val().isValid() or result.val().Volume() <= 0:
        raise ValueError('文字轮廓不能构成有效实体。')
    return result
