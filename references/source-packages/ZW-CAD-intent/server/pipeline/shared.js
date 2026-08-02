export const DEFAULT_PARAMETERS = Object.freeze({
  wall_thickness: 2.4,
  inner_length_x: 0,
  inner_width_y: 0,
  inner_height_z: 0,
  clearance: 1.2,
  hardware_gap: 5,
  edge_clearance: 8,
  lid_thickness: 3,
  lid_lip_height: 4,
  lid_clearance: 0.35,
  corner_radius: 5,
  floor_thickness: 2.4,
  min_wall_thickness: 1.6,
  screw_boss_diameter: 8,
  screw_hole_diameter: 2.2,
  usb_c_margin: 0.8,
  screen_window_margin: 0.8,
  button_hole_margin: 0.7,
  vent_count: 7,
});

export function isPositiveNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0;
}

export function isNonNegativeNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0;
}

export function isFiniteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number);
}

export function within(value, min, max) {
  return Number.isFinite(value) && value >= min - 0.25 && value <= max + 0.25;
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function normalizeString(value) {
  return typeof value === 'string' ? value.trim() : '';
}

export function normalizeStringArray(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim()))];
}

export function normalizeNumberMap(value) {
  if (!isPlainObject(value)) return {};
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    const number = Number(item);
    if (Number.isFinite(number)) result[key] = number;
  }
  return result;
}

export const SUPPORTED_MOUNT_SURFACES = Object.freeze(['base_floor', 'lid_inner', 'lid_outer']);

export function normalizeHardwareFaceOverrides(value) {
  if (!isPlainObject(value)) return {};
  const allowed = new Set(SUPPORTED_MOUNT_SURFACES);
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    const hardwareId = normalizeString(key);
    const face = normalizeString(item);
    if (hardwareId && allowed.has(face)) result[hardwareId] = face;
  }
  return result;
}

export function normalizeHardwareRotationOverrides(value) {
  if (!isPlainObject(value)) return {};
  const allowed = new Set([0, 90, 180, 270]);
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    const hardwareId = normalizeString(key);
    const rotation = Number(item);
    if (hardwareId && allowed.has(rotation)) result[hardwareId] = rotation;
  }
  return result;
}

export function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function stripPythonStringLiterals(code = '') {
  let result = '';
  let index = 0;
  while (index < code.length) {
    const quote = code[index];
    const triple = code.slice(index, index + 3);
    if (triple === '"""' || triple === "'''") {
      const end = code.indexOf(triple, index + 3);
      result += '""';
      index = end === -1 ? code.length : end + 3;
      continue;
    }
    if (quote === '"' || quote === "'") {
      result += '""';
      index += 1;
      while (index < code.length) {
        if (code[index] === '\\') {
          index += 2;
          continue;
        }
        if (code[index] === quote) {
          index += 1;
          break;
        }
        index += 1;
      }
      continue;
    }
    result += quote;
    index += 1;
  }
  return result;
}

export function round(value, precision = 2) {
  const factor = 10 ** precision;
  return Math.round(Number(value) * factor) / factor;
}
