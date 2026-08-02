import { hasBridgeCapability } from "./bridgeLease";

export type HostKind = "web" | "tauri";

export interface PlatformCapabilities {
  host: HostKind;
  browserUpload: boolean;
  nativeFilePicker: boolean;
  localFileRead: boolean;
  localFileWrite: boolean;
  credentialStore: boolean;
  nativeWindow: boolean;
  shellExecution: boolean;
  localToolExecution: boolean;
  serialScan: boolean;
  serialConnection: boolean;
  deviceUpload: boolean;
  deviceFlash: boolean;
  localCadExecution: boolean;
  experimentalWebSerial: boolean;
}

const WEB_CAPABILITIES: PlatformCapabilities = Object.freeze({
  host: "web",
  browserUpload: true,
  nativeFilePicker: false,
  localFileRead: false,
  localFileWrite: false,
  credentialStore: false,
  nativeWindow: false,
  shellExecution: false,
  localToolExecution: false,
  serialScan: false,
  serialConnection: false,
  deviceUpload: false,
  deviceFlash: false,
  localCadExecution: false,
  experimentalWebSerial: false,
});

const TAURI_CAPABILITIES: PlatformCapabilities = Object.freeze({
  host: "tauri",
  browserUpload: true,
  nativeFilePicker: false,
  localFileRead: false,
  localFileWrite: false,
  credentialStore: true,
  nativeWindow: true,
  shellExecution: false,
  localToolExecution: true,
  serialScan: true,
  serialConnection: true,
  deviceUpload: true,
  deviceFlash: true,
  localCadExecution: true,
  experimentalWebSerial: false,
});

interface TauriWindow extends Window {
  __TAURI_INTERNALS__?: unknown;
  __TAURI__?: unknown;
}

export function detectHost(
  target: Window | undefined = globalThis.window,
  configuredHost: string | undefined = import.meta.env.VITE_ZHANGWEN_HOST
): HostKind {
  if (configuredHost === "web" || configuredHost === "tauri") return configuredHost;
  if (!target) return "web";
  const tauriWindow = target as TauriWindow;
  return tauriWindow.__TAURI_INTERNALS__ || tauriWindow.__TAURI__ ? "tauri" : "web";
}

export function platformCapabilities(
  host: HostKind = detectHost()
): PlatformCapabilities {
  if (host === "tauri") return TAURI_CAPABILITIES;
  const experimentalWebSerial = Boolean(
    globalThis.isSecureContext === true &&
    typeof globalThis.navigator !== "undefined" &&
    "serial" in globalThis.navigator,
  );
  if (
    !hasBridgeCapability("cad.local") &&
    !hasBridgeCapability("device.serial") &&
    !hasBridgeCapability("device.upload") &&
    !experimentalWebSerial
  ) return WEB_CAPABILITIES;
  return Object.freeze({
    ...WEB_CAPABILITIES,
    serialScan: hasBridgeCapability("device.serial"),
    serialConnection: hasBridgeCapability("device.serial"),
    deviceUpload: hasBridgeCapability("device.upload"),
    localCadExecution: hasBridgeCapability("cad.local"),
    experimentalWebSerial,
  });
}

export const currentPlatformCapabilities = platformCapabilities();
