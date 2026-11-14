"""Fixed subprocess entry: validate JSON, build bounded primitives and export."""
import json
import sys
from pathlib import Path

import cadquery as cq

from .design_specs import DesignSpec


def build(spec, output, scale):
    result = None
    for part in spec.solid:
        from .solid_geometry import build_piece
        piece = build_piece(part, scale)
        result = piece if result is None else result.union(piece) if part.operation == 'add' else result.cut(piece)
    result = result.clean()
    if not result.solids().size() or not result.val().isValid() or result.val().Volume() <= 0:
        raise ValueError('布尔运算未形成有效实体。')
    bounds = result.val().BoundingBox()
    size = [bounds.xlen, bounds.ylen, bounds.zlen]
    if max(size) > 2000:
        raise ValueError('生成实体超出尺寸上限。')
    cq.exporters.export(result, str(output / 'model.step'))
    cq.exporters.export(result, str(output / 'model.stl'), tolerance=.1, angularTolerance=.2)
    print(json.dumps({'size': size, 'volume': result.val().Volume(), 'solids': result.solids().size()}))


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    data = json.loads((folder / 'design-spec.json').read_text(encoding='utf-8'))
    scale = data['scale']
    if not isinstance(scale, (int, float)) or not .1 <= scale <= 5:
        raise ValueError('缩放范围为0.1到5。')
    build(DesignSpec.model_validate(data['spec']).check_kind('model'), folder, scale)
