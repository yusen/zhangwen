"""Portable text engraving outlines from the bundled, OFL-licensed CJK font."""
from functools import lru_cache
import math
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

FONT = Path(__file__).resolve().parents[4] / 'resources/fonts/NotoSansSC.ttf'


@lru_cache(maxsize=1)
def font():
    return TTFont(FONT, lazy=False)


class ContourPen(BasePen):
    def __init__(self, glyphs, tolerance):
        super().__init__(glyphs)
        self.tolerance = tolerance
        self.contours, self.current = [], []

    def _moveTo(self, point):
        self.current = [point]

    def _lineTo(self, point):
        self.current.append(point)

    def flatten(self, controls, depth=0):
        start, end = controls[0], controls[-1]
        dx, dy = end[0]-start[0], end[1]-start[1]
        length = math.hypot(dx, dy)
        deviation = max((abs(dx*(p[1]-start[1])-dy*(p[0]-start[0]))/length if length else math.dist(p, start)) for p in controls[1:-1])
        if deviation <= self.tolerance or depth >= 12:
            self.current.append(end)
            return
        levels = [controls]
        while len(levels[-1]) > 1:
            levels.append([((a[0]+b[0])/2, (a[1]+b[1])/2) for a,b in zip(levels[-1], levels[-1][1:])])
        self.flatten([level[0] for level in levels], depth+1)
        self.flatten([level[-1] for level in reversed(levels)], depth+1)

    def _curveToOne(self, a, b, end):
        self.flatten([self._getCurrentPoint(), a, b, end])

    def _qCurveToOne(self, a, end):
        self.flatten([self._getCurrentPoint(), a, end])

    def _closePath(self):
        if self.current and self.current[-1] == self.current[0]:
            self.current.pop()
        if len(self.current) >= 3:
            self.contours.append(self.current)
        self.current = []

    def _endPath(self):
        raise ValueError('字体存在开放轮廓，不能生成雕刻区域。')


@lru_cache(maxsize=128)
def outlines(text, height):
    """Ink bounds start at (0,0), Y down; height is the actual ink height in mm."""
    if not text.strip() or len(text) > 40 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError('文字应为1至40个可显示字符，暂不支持换行和控制字符。')
    face = font()
    cmap = face.getBestCmap()
    if any(ord(c) not in cmap for c in text):
        raise ValueError('所选字体缺少部分字符，请使用常用中文、英文、数字或标点。')
    glyphs = face.getGlyphSet(location={'wght':400})
    run, offset, bounds = [], 0., []
    for char in text:
        glyph = glyphs[cmap[ord(char)]]
        pen = BoundsPen(glyphs); glyph.draw(pen)
        if pen.bounds:
            x0,y0,x1,y1 = pen.bounds
            bounds.append((x0+offset,y0,x1+offset,y1))
        run.append((glyph,offset))
        offset += glyph.width
    if not bounds:
        raise ValueError('文字没有可雕刻的轮廓。')
    x0,y0,x1,y1 = min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)
    scale = height/(y1-y0)
    contours = []
    for glyph, offset in run:
        pen = ContourPen(glyphs, .02/scale); glyph.draw(pen)
        contours.extend([[(round((x+offset-x0)*scale,6),round((y1-y)*scale,6)) for x,y in path] for path in pen.contours])
    if len(contours) > 1500 or sum(len(p) for p in contours) > 60000:
        raise ValueError('文字轮廓过于复杂，请减少本次字符数量。')
    return round((x1-x0)*scale,6), contours


def placed(shape):
    _, paths = outlines(shape.text, shape.fontSize)
    return [[[round(x+shape.x,6),round(y+shape.y,6)] for x,y in contour] for contour in paths]


def svg_path(shape):
    return ' '.join('M'+' L'.join(f'{x},{y}' for x,y in contour)+' Z' for contour in placed(shape))
