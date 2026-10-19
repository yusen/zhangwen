import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const libraryPath = path.join(__dirname, 'data', 'hardware-library.json');

const library = JSON.parse(readFileSync(libraryPath, 'utf8'));
const profilesById = new Map(library.profiles.map((profile) => [profile.id, deepFreeze(profile)]));

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
