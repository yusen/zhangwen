import { readFileSync, realpathSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const resourceRoot = path.resolve(__dirname, '../../../resources');
const resourceIndex = JSON.parse(readFileSync(path.join(resourceRoot, 'hardware-resources.json'), 'utf8'));
if (resourceIndex.schema !== 'zhangwen.hardware-resources/v1') throw new Error('Invalid hardware resource index');
const library = {...resourceIndex.structure, profiles: resourceIndex.structure.profiles.map(entry => {
  const target = path.resolve(resourceRoot, entry.path);
  if (!target.startsWith(resourceRoot + path.sep) || realpathSync(target) !== target) throw new Error('Hardware profile path outside resources');
  const raw = readFileSync(target);
  if (createHash('sha256').update(raw).digest('hex') !== resourceIndex.structureFiles[entry.path]) throw new Error('Hardware profile digest mismatch');
  const profile = JSON.parse(raw.toString('utf8'));
  if (profile.id !== entry.id) throw new Error('Hardware profile identity mismatch');
  if (entry.skillName && resourceIndex.modules[entry.skillName]?.componentId !== entry.componentId) throw new Error('Hardware component identity mismatch');
  return {...profile, componentId: entry.componentId};
})};
const profilesById = new Map(library.profiles.map((profile) => [profile.id, deepFreeze(profile)]));
if (profilesById.size !== library.profiles.length) throw new Error('Duplicate hardware profile identity');

export function listHardwareLibrary() {
  return {
    version: library.version,
    units: library.units,
    coordinate_system: library.coordinate_system,
    profiles: library.profiles.map(summarizeHardwareProfile),
  };
}

export function getHardwareProfile(id) {
  return profilesById.get(id) || null;
}

export function getHardwareProfiles(ids = []) {
  return ids.map(getHardwareProfile).filter(Boolean);
}

export function createHardwareResolver(customProfiles = []) {
  const customById = new Map(
    normalizeCustomProfiles(customProfiles).map((profile) => [profile.id, deepFreeze(profile)]),
  );
  return {
    getHardwareProfile(id) {
      return customById.get(id) || getHardwareProfile(id);
    },
    getHardwareProfiles(ids = []) {
      return ids.map((id) => customById.get(id) || getHardwareProfile(id)).filter(Boolean);
    },
    listCustomProfiles() {
      return [...customById.values()];
    },
    listProfiles() {
      return [...library.profiles, ...customById.values()];
    },
  };
}

export function findHardwareByRole(role) {
  const normalized = normalizeText(role);
  return library.profiles.filter((profile) => {
    const roles = Array.isArray(profile.roles) ? profile.roles : [];
    return (
      normalizeText(profile.category) === normalized ||
      roles.some((item) => normalizeText(item) === normalized)
    );
  });
}

export function getHardwareLibrarySummary() {
  return library.profiles.map((profile) => ({
    id: profile.id,
    name: profile.name,
    category: profile.category,
    roles: profile.roles || [],
    thumbnail_url: profile.thumbnail_url || '',
    dimensions_mm: profile.dimensions_mm,
    source_status: profile.source_status,
  }));
}

export function summarizeHardwareProfile(profile) {
  return {
    id: profile.id,
    name: profile.name,
    category: profile.category,
    roles: profile.roles || [],
    thumbnail_url: profile.thumbnail_url || '',
    dimensions_mm: profile.dimensions_mm,
    coordinate_system: profile.coordinate_system,
    mounting: profile.mounting,
    opening: profile.opening || [],
    keepouts: profile.keepouts || [],
    cad_reference: profile.cad_reference,
    source_status: profile.source_status,
  };
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase();
}

function normalizeCustomProfiles(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter((profile) => profile && typeof profile === 'object' && typeof profile.id === 'string')
    .map((profile) => ({
      ...profile,
      roles: Array.isArray(profile.roles) ? profile.roles : [],
      opening: Array.isArray(profile.opening) ? profile.opening : [],
      keepouts: Array.isArray(profile.keepouts) ? profile.keepouts : [],
      source_status: profile.source_status || '用户临时提供，未写入硬件库',
    }));
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object') return value;
  Object.freeze(value);
  for (const child of Object.values(value)) {
    deepFreeze(child);
  }
  return value;
}
