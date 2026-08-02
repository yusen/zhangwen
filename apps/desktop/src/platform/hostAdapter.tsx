import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { platformCapabilities, type PlatformCapabilities } from "./capabilities";
import { BRIDGE_LEASE_CHANGED_EVENT } from "./bridgeLease";

export interface HostAdapter {
  capabilities: PlatformCapabilities;
  unsupportedMessage(capability: keyof PlatformCapabilities): string | null;
  require(capability: keyof PlatformCapabilities): void;
}

export class UnsupportedHostCapabilityError extends Error {
  readonly capability: keyof PlatformCapabilities;

  constructor(capability: keyof PlatformCapabilities, message: string) {
    super(message);
    this.name = "UnsupportedHostCapabilityError";
    this.capability = capability;
  }
}

const UNSUPPORTED_MESSAGES: Partial<Record<keyof PlatformCapabilities, string>> = {
  credentialStore: "浏览器不会读取或保存模型密钥；请在本地后端配置模型服务。",
  nativeFilePicker: "当前浏览器模式不支持原生文件选择器。",
  localFileRead: "当前浏览器模式不支持任意本地目录读取。",
  localFileWrite: "当前浏览器模式不支持写入指定本地路径。",
  nativeWindow: "当前浏览器模式不支持原生窗口能力。",
  shellExecution: "当前浏览器模式不支持本地 Shell。",
  localToolExecution: "当前浏览器模式不支持受控本地工具执行。",
  serialScan: "当前浏览器模式不支持本地串口扫描。",
  serialConnection: "当前浏览器模式不支持本地串口连接。",
  deviceUpload: "当前浏览器模式不支持设备上传。",
  deviceFlash: "当前浏览器模式不支持固件烧录。",
  localCadExecution: "当前浏览器模式不支持本地 CAD 执行。",
};

export function createHostAdapter(
  capabilities: PlatformCapabilities = platformCapabilities()
): HostAdapter {
  const unsupportedMessage = (
    capability: keyof PlatformCapabilities
  ): string | null => {
    const value = capabilities[capability];
    return value === false
      ? UNSUPPORTED_MESSAGES[capability] ?? "当前宿主不支持此能力。"
      : null;
  };
  return {
    capabilities,
    unsupportedMessage,
    require(capability) {
      const message = unsupportedMessage(capability);
      if (message) throw new UnsupportedHostCapabilityError(capability, message);
    },
  };
}

const HostAdapterContext = createContext<HostAdapter | null>(null);

export function HostAdapterProvider({
  adapter,
  children,
}: {
  adapter?: HostAdapter;
  children: ReactNode;
}) {
  const [bridgeRevision, setBridgeRevision] = useState(0);
  useEffect(() => {
    const changed = () => setBridgeRevision((value) => value + 1);
    globalThis.addEventListener?.(BRIDGE_LEASE_CHANGED_EVENT, changed);
    return () => globalThis.removeEventListener?.(BRIDGE_LEASE_CHANGED_EVENT, changed);
  }, []);
  const value = useMemo(
    () => adapter ?? createHostAdapter(),
    [adapter, bridgeRevision],
  );
  return createElement(
    HostAdapterContext.Provider,
    { value },
    children
  );
}

export function useHostAdapter(): HostAdapter {
  return useContext(HostAdapterContext) ?? createHostAdapter();
}
