"""Convert declarative laser curves to the same bounded paths for preview/export."""
import math

TOLERANCE = .05  # Maximum chord deviation in millimetres.


def normalize_curve(value):
    if not isinstance(value, dict) or not isinstance(value.get('kind'), str) or value.get('kind') not in {'arc', 'ellipse', 'bezier'}:
        return value
    data = dict(value)
    kind = data['kind']
    allowed = {'kind','operation','x','y','width','height','radius','points','closed','text','fontSize','startAngle','endAngle','rotation'}
    if set(data)-allowed:
        raise ValueError('曲线包含未知字段。')
    if 'closed' in data and not isinstance(data['closed'], bool):
        raise ValueError('closed必须为布尔值。')
    def number(key, default):
        raw = data.get(key, default)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError('曲线参数必须为数值。')
        n = float(raw)
        if not math.isfinite(n) or abs(n) > 10000:
            raise ValueError('曲线参数必须是有限数值。')
        return n
    if kind == 'bezier':
        controls = data.get('points', [])
        if not isinstance(controls, list) or len(controls) not in {3, 4} or any(not isinstance(p, (list,tuple)) or len(p) != 2 or not all(isinstance(n, (int, float)) and math.isfinite(n) and abs(n) <= 1000 for n in p) for p in controls):
            raise ValueError('贝塞尔曲线需要三个或四个二维控制点。')
        acceleration = (2 if len(controls) == 3 else 6) * max(math.hypot(c[0]-2*b[0]+a[0], c[1]-2*b[1]+a[1]) for a,b,c in zip(controls, controls[1:], controls[2:]))
        count = max(2, math.ceil(math.sqrt(acceleration/(8*TOLERANCE))))
        points = []
        for i in range(count+1):
            t = i/count
            level = controls
            while len(level) > 1:
                level = [[(1-t)*a[j]+t*b[j] for j in (0,1)] for a,b in zip(level, level[1:])]
            points.append(level[0])
        closed = data.get('closed', False)
    else:
        cx, cy = number('x', 0), number('y', 0)
        rx = number('radius', 1) if kind == 'arc' else number('width', 1)/2
        ry = rx if kind == 'arc' else number('height', 1)/2
        if min(rx, ry) <= 0 or max(rx, ry) > 1000:
            raise ValueError('圆弧或椭圆半径须大于零且不超过1000毫米。')
        if any(abs(number(k, default)) > 360 for k,default in [('startAngle',0),('endAngle',360),('rotation',0)]):
            raise ValueError('曲线角度须在±360度内。')
        start = math.radians(number('startAngle', 0))
        sweep = math.radians(number('endAngle', 360))-start
        if not 0 < abs(sweep) <= 2*math.pi + 1e-9:
            raise ValueError('曲线起止角之差须大于零且不超过360度。')
        rotation = math.radians(number('rotation', 0))
        step = 2*math.acos(max(-1, 1-TOLERANCE/max(rx,ry)))
        count = max(4, math.ceil(abs(sweep)/step))
        points = []
        for i in range(count+1):
            angle = start+sweep*i/count
            x,y = rx*math.cos(angle),ry*math.sin(angle)
            points.append([cx+x*math.cos(rotation)-y*math.sin(rotation),cy+x*math.sin(rotation)+y*math.cos(rotation)])
        closed = abs(abs(sweep)-2*math.pi) < 1e-8
        if data.get('closed') is True:
            closed = True  # Partial arc plus closing chord.
        if abs(abs(sweep)-2*math.pi) < 1e-8:
            points.pop()
    return {'kind':'polyline', 'operation':data.get('operation','cut'),
            'points':[[round(n,6) for n in p] for p in points], 'closed':closed}
