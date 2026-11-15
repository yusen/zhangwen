"""Trusted geometry compiler for data-only solid operations, also used by cases."""


def piece_lines(part, scale=1, name='piece'):
    """Emit only fixed CadQuery calls with validated numeric literal arguments."""
    sx, sy, sz = [round(n*scale, 6) for n in part.size]
    points = [[round(n*scale,6) for n in p] for p in part.profile]
    prefix = name+' = '
    kind = part.kind
    if kind == 'box':
        lines = [prefix+f'cq.Workplane("XY").box({sx!r}, {sy!r}, {sz!r})']
    elif kind == 'cylinder':
        lines = [prefix+f'cq.Workplane("XY").cylinder({sz!r}, {sx/2!r})']
    elif kind == 'sphere':
        lines = [prefix+f'cq.Workplane("XY").sphere({sx/2!r})']
    elif kind == 'cone':
        lines = [prefix+f'cq.Workplane("XY").newObject([cq.Solid.makeCone({sx/2!r}, {part.topDiameter*scale/2!r}, {sz!r}, cq.Vector(0, 0, {-sz/2!r}))])']
    elif kind == 'torus':
        lines = [prefix+f'cq.Workplane("XY").newObject([cq.Solid.makeTorus({(sx-sz)/2!r}, {sz/2!r})])']
    elif kind == 'extrude':
        lines = [prefix+f'cq.Workplane("XY").polyline({points!r}).close().extrude({sz!r}).translate((0, 0, {-sz/2!r}))']
    elif kind == 'revolve':
        lines = [prefix+f'cq.Workplane("XZ").polyline({points!r}).close().revolve({part.angle!r}, (0, 0), (0, 1))']
    elif kind == 'loft':
        lines = [prefix+'cq.Workplane("XY")']
        last_z = 0
        for section in part.sections:
            z = section.z*scale
            profile = [[round(n*scale,6) for n in p] for p in section.points]
            lines.append(prefix+f'{name}.workplane(offset={z-last_z!r}).polyline({profile!r}).close()')
            last_z = z
        lines.append(prefix+f'{name}.loft(ruled={part.ruled!r}, combine=False)')
    else:
        raise ValueError('未知实体类型。')
    if part.fillet:
        lines.append(prefix+f'{name}.edges().fillet({part.fillet*scale!r})')
    if part.chamfer:
        lines.append(prefix+f'{name}.edges().chamfer({part.chamfer*scale!r})')
    for axis, angle in zip([(1,0,0),(0,1,0),(0,0,1)],part.rotation):
        if angle:
            lines.append(prefix+f'{name}.rotate((0, 0, 0), {axis!r}, {angle!r})')
    lines.append(prefix+f'{name}.translate({tuple(round(n*scale,6) for n in part.center)!r})')
    return lines


def build_piece(part, scale=1):
    # This source is entirely produced above from validated data; never accept
    # source strings from the model, a project file, or an API request.
    import cadquery as cq
    namespace = {'cq':cq, '__builtins__':{}}
    exec('\n'.join(piece_lines(part, scale)), namespace)
    return namespace['piece']
