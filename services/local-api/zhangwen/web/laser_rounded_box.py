"""Nominal living-hinge box: two inset lids and a continuous neutral-axis wall.

All dimensions are millimetres. Straight-edge tabs on lids match wall rebates;
corner slits are intentional single open cuts, with staggered material bridges.
No kerf offset or prediction of material bendability/physical fit is applied.
"""
import math

DEFAULTS = dict(width=50, depth=50, height=50, thickness=3, corner_radius=12,
                tab_width=5, slot_spacing=1.2, slot_bridge=2, slot_rows=2,
                top_lid=1, bottom_lid=1)


def drawing(width, depth, height, thickness, corner_radius, tab_width,
            slot_spacing, slot_bridge, slot_rows, top_lid, bottom_lid, material,
            pattern_version=1):
    w, d, h, t, r = width, depth, height, thickness, corner_radius
    numbers = [w, d, h, t, r, tab_width, slot_spacing, slot_bridge, slot_rows]
    if not all(math.isfinite(n) for n in numbers):
        raise ValueError('圆角盒参数必须是有限数值。')
    if not .8 <= t <= 12 or min(w, d) < 8*t or h < 4*t + 4*slot_bridge:
        raise ValueError('圆角盒宽深至少为板厚8倍，高度至少为4倍板厚加4倍切缝桥宽；板厚0.8至12毫米。')
    if not 2*t <= r <= (min(w, d)-5*t)/2:
        raise ValueError('圆角半径至少为板厚2倍，圆角之间还需保留至少5倍板厚的直边用于榫接。')
    if not .6 <= slot_spacing <= 8 or not .8 <= slot_bridge <= 8 or not 1 <= slot_rows <= 6 or int(slot_rows) != slot_rows:
        raise ValueError('切缝间距0.6至8毫米，桥宽0.8至8毫米，纵向切缝段数为1至6的整数。')
    if not t <= tab_width <= min(w-2*r, d-2*r)/3:
        raise ValueError('目标榫宽至少为板厚，且不大于较短直边的三分之一。')
    a, b, neutral_radius = w-2*r, d-2*r, r-t/2
    arc = math.pi*neutral_radius/2
    perimeter = 2*(a+b)+4*arc
    if perimeter+10 > 1000:
        raise ValueError('连续围板展开后超出1000毫米画布，请缩小宽深或圆角。')

    def tabs(length):
        # 4k+1 intervals leave material at corners and at the top-centre seam.
        options = [n for n in (5, 9, 13) if length/n >= t]
        count = min(options, key=lambda n: abs(length/n-tab_width))
        return [(length*i/count, length*(i+1)/count) for i in range(1, count, 2)]

    xtabs, ytabs = tabs(a), tabs(b)
    wall_tabs = []
    for lo, hi in xtabs:
        if lo >= a/2:
            wall_tabs.append((lo-a/2, hi-a/2))
        else:
            wall_tabs.append((perimeter-a/2+lo, perimeter-a/2+hi))
        wall_tabs.append((a/2+2*arc+b+a-hi, a/2+2*arc+b+a-lo))
    for lo, hi in ytabs:
        wall_tabs.append((a/2+arc+lo, a/2+arc+hi))
        wall_tabs.append((a/2+3*arc+a+b+b-hi, a/2+3*arc+a+b+b-lo))
    wall_tabs.sort()
    shapes = []

    def poly(points, ox, oy):
        output = []
        for x, y in points:
            point = [round(x+ox, 6), round(y+oy, 6)]
            if not output or point != output[-1]:
                output.append(point)
        if output[0] == output[-1]:
            output.pop()
        shapes.append(dict(kind='polyline', operation='cut', closed=True, points=output))

    # Plate core follows the inside of the wall; tabs reach the outside plane.
    lid = []
    ri = r-t
    segments = max(6, math.ceil((math.pi/2)/(2*math.acos(1-.05/ri))))
    if segments > 32:
        raise ValueError('圆角轮廓采样超限，请缩小半径。')
    for start, direction, outward, spans, length, center, start_angle in [
        ((r,t),(1,0),(0,-t),xtabs,a,(w-r,r),-math.pi/2),
        ((w-t,r),(0,1),(t,0),ytabs,b,(w-r,d-r),0),
        ((w-r,d-t),(-1,0),(0,t),xtabs,a,(r,d-r),math.pi/2),
        ((t,d-r),(0,-1),(-t,0),ytabs,b,(r,r),math.pi),
    ]:
        def point(s, extension=0):
            return (start[0]+direction[0]*s+outward[0]*extension,
                    start[1]+direction[1]*s+outward[1]*extension)
        lid.append(point(0))
        for lo, hi in spans:
            lid.extend([point(lo), point(lo,1), point(hi,1), point(hi)])
        lid.append(point(length))
        for i in range(1, segments+1):
            angle = start_angle+math.pi*i/(2*segments)
            lid.append((center[0]+ri*math.cos(angle), center[1]+ri*math.sin(angle)))
    lids = int(top_lid)+int(bottom_lid)
    for i in range(lids):
        poly(lid, 5+i*(w+5), 5)
    wall_y = d+10 if lids else 5
    wall = [(0,0)]
    if top_lid:
        for lo, hi in wall_tabs:
            wall.extend([(lo,0),(lo,t),(hi,t),(hi,0)])
    wall.extend([(perimeter,0),(perimeter,h)])
    if bottom_lid:
        for lo, hi in reversed(wall_tabs):
            wall.extend([(hi,h),(hi,h-t),(lo,h-t),(lo,h)])
    wall.append((0,h))
    poly(wall, 5, wall_y)

    # Four equal quarter-circle zones along the neutral axis. Keep v1 solely
    # for exact validation of already persisted drawings; new designs use v2.
    if pattern_version not in (1, 2):
        raise ValueError('不支持的圆角盒切缝版本。')
    columns = math.floor(arc/slot_spacing)-1
    if columns < 3:
        raise ValueError('当前圆角放不下至少三列弯折切缝，请减小间距或增大圆角。')
    rows = int(slot_rows)
    z0, z1 = (t+slot_bridge, h-t-slot_bridge) if pattern_version == 1 else (0, h)
    pitch = (z1-z0)/rows
    if pitch < 3*slot_bridge:
        raise ValueError('纵向切缝太密，剩余桥宽不足；请减少段数、桥宽或增加高度。')
    corners = [a/2, a/2+arc+b, a/2+2*arc+b+a, a/2+3*arc+2*b+a]
    for offset in corners:
        for j in range(columns):
            x = 5+offset+arc*(j+1)/(columns+1)
            shift = -.5 if j%2 else 0
            for i in range(rows+1):
                raw_lo, raw_hi = z0+(i+shift)*pitch, z0+(i+1+shift)*pitch
                lo = max(z0, raw_lo)+slot_bridge/2
                hi = min(z1, raw_hi)-slot_bridge/2
                if pattern_version == 2:
                    # Staggered columns open onto both free edges. Their
                    # neighbours retain end bridges, so strips remain joined.
                    if raw_lo <= z0:
                        lo = z0 if j % 2 else z0+slot_bridge
                    if raw_hi >= z1:
                        hi = z1 if j % 2 else z1-slot_bridge
                if hi-lo < slot_bridge:
                    continue
                shapes.append(dict(kind='line', operation='cut', closed=False,
                                   points=[[round(x,6), round(wall_y+lo,6)], [round(x,6),round(wall_y+hi,6)]]))
    if len(shapes) > 512:
        raise ValueError('弯折切缝超过512条路径上限，请增大间距或减少纵向段数。')
    sheet_width = max(perimeter+10, lids*(w+5)+5)
    sheet_height = wall_y+h+5
    if max(sheet_width, sheet_height) > 1000:
        raise ValueError('圆角盒排版超出1000毫米画布，请缩小尺寸。')
    return dict(width=round(sheet_width,6), height=round(sheet_height,6), thickness=t,
                material=material, kerf=0, shapes=shapes)
