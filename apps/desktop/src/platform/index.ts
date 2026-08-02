export {
  currentPlatformCapabilities,
  detectHost,
  platformCapabilities,
  type HostKind,
  type PlatformCapabilities,
} from "./capabilities";
export {
  createHostAdapter,
  HostAdapterProvider,
  UnsupportedHostCapabilityError,
  useHostAdapter,
  type HostAdapter,
} from "./hostAdapter";
export {
  BRIDGE_LEASE_CHANGED_EVENT,
  clearActiveBridgeLease,
  getActiveBridgeLease,
  hasBridgeCapability,
  setActiveBridgeLease,
  type ActiveBridgeLease,
} from "./bridgeLease";
