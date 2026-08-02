export interface ActiveBridgeLease {
  token: string;
  id: string;
  projectId: string;
  origin: string;
  capabilities: string[];
  expiresAt: string;
}

export const BRIDGE_LEASE_CHANGED_EVENT = "zhangwen:bridge-lease-changed";

let activeLease: ActiveBridgeLease | null = null;

export function getActiveBridgeLease(): ActiveBridgeLease | null {
  if (!activeLease) return null;
  if (Date.parse(activeLease.expiresAt) <= Date.now()) {
    activeLease = null;
    return null;
  }
  return activeLease;
}

export function setActiveBridgeLease(lease: ActiveBridgeLease): void {
  activeLease = { ...lease, capabilities: [...lease.capabilities] };
  globalThis.dispatchEvent?.(new Event(BRIDGE_LEASE_CHANGED_EVENT));
}

export function clearActiveBridgeLease(notify = true): void {
  activeLease = null;
  if (notify) globalThis.dispatchEvent?.(new Event(BRIDGE_LEASE_CHANGED_EVENT));
}

export function hasBridgeCapability(capability: string): boolean {
  return getActiveBridgeLease()?.capabilities.includes(capability) ?? false;
}
