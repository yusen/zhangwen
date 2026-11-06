type Vector = readonly [number, number, number];
const dot = (a: Vector, b: Vector) => a.reduce((sum, n, i) => sum + n * b[i], 0);
const cross = (a: Vector, b: Vector): Vector => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a: Vector): Vector => { const length = Math.hypot(...a); return a.map(n => n / length) as unknown as Vector; };

/** Fit every box corner in the perspective viewport, including depth foreshortening. */
export function modelFrameDistance(size: Vector, direction: Vector, up: Vector, aspect: number, fov: number): number {
  const outward = unit(direction), right = unit(cross(up, outward)), vertical = cross(outward, right);
  const tanV = Math.tan(fov * Math.PI / 360), tanH = tanV * Math.max(aspect, .01);
  let distance = 1;
  for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
    const corner: Vector = [x * size[0] / 2, y * size[1] / 2, z * size[2] / 2];
    distance = Math.max(distance, dot(corner, outward) + Math.max(Math.abs(dot(corner, right)) / tanH, Math.abs(dot(corner, vertical)) / tanV) / .82);
  }
  return distance;
}
