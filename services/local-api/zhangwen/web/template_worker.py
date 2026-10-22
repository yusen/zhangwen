"""Only execute packaged, checksum-verified template IDs; no imported project code."""
import json
import math
from pathlib import Path
import sys

import cadquery as cq

from .builtin_templates import TEMPLATES, checked_source
from .template_edits import checked_spec, render_source


def build(ident, output):
    item = TEMPLATES[ident]
    source = checked_source(item).read_text(encoding='utf-8-sig')
    plan_file = output / 'template-edit.json'
    spec = checked_spec(json.loads(plan_file.read_text(encoding='utf-8')) if plan_file.exists() else {'title': item['title']}, item, source)
    ns = {'show_object': lambda *args, **kwargs: None, '__name__': '__main__'}
    exec(compile(render_source(source, spec, item), str(checked_source(item)), 'exec'), ns)
    parts, shapes = [], []
    for part in item['parts']:
        name, _, index = part['object'].partition(':')
        obj = ns[name] if not index else ns[name][int(index)]
        shape = obj.val() if isinstance(obj, cq.Workplane) else obj
        if not shape.isValid() or not shape.Solids() or (part['printable'] and len(shape.Solids()) != 1) or shape.Volume() <= 0:
            raise ValueError('Template part is not a valid single solid')
        box = shape.BoundingBox()
        size = [box.xlen, box.ylen, box.zlen]
        if any(not math.isfinite(n) or not 0 < n <= 2000 for n in size):
            raise ValueError('Template dimensions exceed bounds')
        normalized = shape.translate(cq.Vector(0, 0, -box.zmin))
        for fmt in (['step', 'stl'] if part['printable'] else ['stl']):
            cq.exporters.export(normalized, str(output / f'template-{part["id"]}.{fmt}'), tolerance=.1, angularTolerance=.2)
        parts.append({**{key: part[key] for key in ['id', 'label', 'printable']},
                      'exportId': f'template_{part["id"]}_stl', 'placement': [0, 0, box.zmin], 'size': [round(n, 3) for n in size]})
        if part['printable']:
            shapes.append(shape)
    box = cq.Compound.makeCompound(shapes).BoundingBox()
    print(json.dumps({'parts': parts, 'printableCount': len(shapes), 'size': [round(n, 3) for n in (box.xlen, box.ylen, box.zlen)]}))


if __name__ == '__main__':
    build(sys.argv[1], Path(sys.argv[2]))
