import type { HostCapabilityLease } from "@zhangwen/contracts";
import {
  clearActiveBridgeLease,
  setActiveBridgeLease,
} from "../platform/bridgeLease";
import { apiGet, apiPost } from "./api";

export interface LocalBridgeStatus {
  protocol: string;
  available: boolean;
  loopbackOnly: boolean;
  leaseTtlSeconds: number;
  capabilities: string[];
}

export interface LocalBridgePairing {
  pairingId: string;
  code: string;
  origin: string;
  projectId: string;
  capabilities: string[];
  expiresAt: string;
}

export interface LocalBridgeLeaseResponse {
  leaseToken: string;
  lease: HostCapabilityLease;
}

export function getLocalBridgeStatus(signal?: AbortSignal): Promise<LocalBridgeStatus> {
  return apiGet<LocalBridgeStatus>("/api/local-bridge/status", signal);
}

export function startLocalBridgePairing(request: {
  origin: string;
  projectId: string;
  capabilities: string[];
}): Promise<LocalBridgePairing> {
  return apiPost<typeof request, LocalBridgePairing>(
    "/api/local-bridge/pairing/start",
    request,
  );
}

export async function claimLocalBridgePairing(request: {
  pairingId: string;
  code: string;
}): Promise<LocalBridgeLeaseResponse> {
  const response = await apiPost<typeof request, LocalBridgeLeaseResponse>(
    "/api/local-bridge/pairing/claim",
    request,
  );
  setActiveBridgeLease({
    token: response.leaseToken,
    id: response.lease.id,
    projectId: response.lease.projectId,
    origin: response.lease.origin,
    capabilities: response.lease.capabilities,
    expiresAt: response.lease.expiresAt,
  });
  return response;
}

export async function revokeLocalBridgeLease(): Promise<void> {
  await apiPost<Record<string, never>, { revoked: boolean }>(
    "/api/local-bridge/revoke",
    {},
  );
  clearActiveBridgeLease();
}
