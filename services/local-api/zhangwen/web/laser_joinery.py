"""Nominal six-panel finger box: deterministic complementary orthogonal paths.

Faces partition the closed rectangular shell. Along each shared edge the same
global coordinate chooses alternating owners; axis priority resolves corners.
No kerf, clearance, machine instructions or physical fit assumptions.
"""
import math


def panels(width, depth, height, thickness):
    dimensions = [width, depth, height]
    if any(not math.isfinite(n) or n < 6 * thickness for n in dimensions):
        raise ValueError('榫齿盒外尺寸须至少为板厚的6倍，保证榫齿与角部连续。')
    counts = []
    for length in dimensions:
        count = min(9, max(3, int(length / (3 * thickness))))
        counts.append(count if count % 2 else count - 1)
    output = []
    for normal in range(3):
        axes = [i for i in range(3) if i != normal]
        u, v = axes
        coords = [sorted(set([0., thickness, dimensions[a] - thickness, dimensions[a]] +
                            [dimensions[a] * i / counts[a] for i in range(1, counts[a])])) for a in axes]
        xs, ys = coords
        edges = set()

        def loses(other, along, coordinate):
            interval = min(counts[along] - 1, int(coordinate / dimensions[along] * counts[along]))
            return (normal > other) == (interval % 2 == 0)

        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                x, y = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                if ((x < thickness or x > dimensions[u] - thickness) and loses(u, v, y) or
                    (y < thickness or y > dimensions[v] - thickness) and loses(v, u, x)):
                    continue
                corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                for start, end in zip(corners, corners[1:] + corners[:1]):
                    if (end, start) in edges:
                        edges.remove((end, start))
                    else:
                        edges.add((start, end))
        outgoing = {a: b for a, b in edges}
        if len(outgoing) != len(edges):
            raise ValueError('榫齿轮廓出现非连续角点，请调整尺寸或板厚。')
        first = min(outgoing)
        path, current = [], first
        while True:
            path.append(current)
            current = outgoing.pop(current)
            if current == first:
                break
        if outgoing:
            raise ValueError('榫齿轮廓不连续，请调整尺寸或板厚。')
        # Remove grid subdivisions but retain every physical right-angle corner.
        points = [[round(xs[i], 6), round(ys[j], 6)] for i, j in path]
        outline = [p for k, p in enumerate(points)
                   if (p[0] - points[k-1][0]) * (points[(k+1) % len(points)][1] - p[1]) !=
                      (p[1] - points[k-1][1]) * (points[(k+1) % len(points)][0] - p[0])]
        for side in (0, 1):
            output.append({'normal': normal, 'side': side, 'axes': axes, 'width': dimensions[u],
                           'height': dimensions[v], 'points': outline})
    return output


def drawing(width, depth, height, thickness, material):
    faces = panels(width, depth, height, thickness)
    shapes, y, max_x = [], 5., 0.
    # Paired opposite faces in three rows; all parts separated by 5 mm.
    for row in range(3):
        x = 5.
        for face in faces[row * 2:row * 2 + 2]:
            shapes.append({'kind': 'polyline', 'closed': True, 'operation': 'cut',
                           'points': [[round(px + x, 6), round(py + y, 6)] for px, py in face['points']]})
            x += face['width'] + 5
        max_x = max(max_x, x)
        y += faces[row * 2]['height'] + 5
    if max_x > 1000 or y > 1000:
        raise ValueError('六块榫齿板排版超出1000毫米画布，请缩小盒子尺寸。')
    return {'width': round(max_x, 6), 'height': round(y, 6), 'thickness': thickness,
            'material': material, 'kerf': 0, 'shapes': shapes}
