import { readFileSync } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const libraryPath = path.join(__dirname, 'data', 'hardware-library.json');

let library = loadHardwareLibraryFromDisk();
let profilesById = buildProfilesById(library);

export function listHardwareLibrary() {
  return {
    version: library.version,
    units: library.units,
    coordinate_system: library.coordinate_system,
    hardware_systems: library.hardware_systems || {},
    profiles: library.profiles.map(summarizeHardwareProfile),
  };
}

export async function addUserCustomHardwareProfile(profile) {
  if (!profile || typeof profile !== 'object') {
    throw new Error('custom hardware profile must be an object');
  }
  if (profile.hardware_system !== 'user_custom') {
    throw new Error('custom hardware profile must use hardware_system="user_custom"');
  }
  if (profilesById.has(profile.id)) {
    throw new Error(`硬件 id 已存在：${profile.id}`);
  }
  const nextLibrary = cloneJson(library);
  nextLibrary.hardware_systems = nextLibrary.hardware_systems || {};
  if (!nextLibrary.hardware_systems.user_custom) {
    nextLibrary.hardware_systems.user_custom = buildUserCustomHardwareSystem();
  }
  nextLibrary.hardware_systems.user_custom.profile_ids = Array.isArray(nextLibrary.hardware_systems.user_custom.profile_ids)
    ? nextLibrary.hardware_systems.user_custom.profile_ids
    : [];
  nextLibrary.hardware_systems.user_custom.profile_ids.push(profile.id);
  nextLibrary.profiles = Array.isArray(nextLibrary.profiles) ? nextLibrary.profiles : [];
  nextLibrary.profiles.push(profile);
  await writeFile(libraryPath, `${JSON.stringify(nextLibrary, null, 2)}\n`, 'utf8');
  library = nextLibrary;
  profilesById = buildProfilesById(library);
  return getHardwareProfile(profile.id);
}

export async function removeUserCustomHardwareProfile(id) {
  const profileId = normalizeText(id);
  if (!profileId || !profileId.startsWith('user_custom_')) {
    throw new Error('only user_custom hardware profiles can be deleted');
  }
  const existing = profilesById.get(profileId);
  if (!existing) {
    throw new Error(`hardware id not found: ${profileId}`);
  }
  if (existing.hardware_system !== 'user_custom') {
    throw new Error('only user_custom hardware profiles can be deleted');
  }

  const nextLibrary = cloneJson(library);
  nextLibrary.profiles = (nextLibrary.profiles || []).filter((profile) => profile.id !== profileId);
  if (nextLibrary.hardware_systems?.user_custom) {
    nextLibrary.hardware_systems.user_custom.profile_ids = (nextLibrary.hardware_systems.user_custom.profile_ids || [])
      .filter((item) => item !== profileId);
  }
  await writeFile(libraryPath, `${JSON.stringify(nextLibrary, null, 2)}\n`, 'utf8');
  library = nextLibrary;
  profilesById = buildProfilesById(library);
  return existing;
}

export function buildUserCustomHardwareSystem() {
  return {
    id: 'user_custom',
    name: '用户自定义硬件',
    description: 'User-created electronic and structural hardware profiles.',
    profile_ids: [],
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
    hardware_system: profile.hardware_system || 'common',
    model_type: profile.model_type || '',
    aliases: Array.isArray(profile.aliases) ? profile.aliases : [],
    model_quality: profile.model_quality || null,
    cadquery_model: profile.cadquery_model || null,
    custom_hardware_type: profile.custom_hardware_type || '',
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
    hardware_system: profile.hardware_system || 'common',
    model_type: profile.model_type || '',
    aliases: Array.isArray(profile.aliases) ? profile.aliases : [],
    model_quality: profile.model_quality || null,
    cadquery_model: profile.cadquery_model || null,
    custom_hardware_type: profile.custom_hardware_type || '',
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

function loadHardwareLibraryFromDisk() {
  const parsed = JSON.parse(readFileSync(libraryPath, 'utf8'));
  parsed.hardware_systems = parsed.hardware_systems || {};
  if (!parsed.hardware_systems.user_custom) {
    parsed.hardware_systems.user_custom = buildUserCustomHardwareSystem();
  }
  return parsed;
}

function buildProfilesById(source) {
  return new Map((source.profiles || []).map((profile) => [profile.id, deepFreeze(profile)]));
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
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
      hardware_system: normalizeText(profile.hardware_system) || 'common',
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
