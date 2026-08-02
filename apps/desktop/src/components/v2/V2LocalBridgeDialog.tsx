import { useEffect, useState } from "react";
import { detectHost, getActiveBridgeLease } from "../../platform";
import {
  claimLocalBridgePairing,
  getLocalBridgeStatus,
  revokeLocalBridgeLease,
  startLocalBridgePairing,
  type LocalBridgePairing,
} from "../../services/localBridgeApi";

export function V2LocalBridgeDialog({
  projectId,
  professionalMode,
  onClose,
}: {
  projectId: string | null;
  professionalMode: boolean;
  onClose: () => void;
}) {
  const host = detectHost();
  const [available, setAvailable] = useState<boolean | null>(null);
  const [pairingId, setPairingId] = useState("");
  const [code, setCode] = useState("");
  const [origin, setOrigin] = useState("http://localhost:5173");
  const [pairing, setPairing] = useState<LocalBridgePairing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lease, setLease] = useState(getActiveBridgeLease());

  useEffect(() => {
    const controller = new AbortController();
    void getLocalBridgeStatus(controller.signal)
      .then((status) => setAvailable(status.available && status.loopbackOnly))
      .catch(() => setAvailable(false));
    return () => controller.abort();
  }, []);

  const start = async () => {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      setPairing(await startLocalBridgePairing({
        origin,
        projectId,
        capabilities: ["cad.local", "device.serial", "device.upload"],
      }));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "创建配对挑战失败。");
    } finally {
      setBusy(false);
    }
  };

  const claim = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await claimLocalBridgePairing({ pairingId, code });
      setLease({
        token: response.leaseToken,
        id: response.lease.id,
        projectId: response.lease.projectId,
        origin: response.lease.origin,
        capabilities: response.lease.capabilities,
        expiresAt: response.lease.expiresAt,
      });
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "连接失败，请重新输入连接码。");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    setError(null);
    try {
      await revokeLocalBridgeLease();
      setLease(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "断开连接失败。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="v2-bridge-backdrop" role="presentation">
      <section className="v2-bridge-dialog" role="dialog" aria-modal="true" aria-label="网页连接">
        <header>
          <div>
            <span className="v2-card-label">{professionalMode ? "Web 本地能力" : "网页版"}</span>
            <h2>{professionalMode ? "Local Bridge" : "连接这台电脑"}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭网页连接">×</button>
        </header>
        <p>{professionalMode
          ? "Bridge 只监听本机回环地址。每次配对只授予当前项目的 CAD、串口和上传能力；不开放 Shell、任意路径、凭据或固件烧录。"
          : "网页版要生成 3D 模型或上传代码，需要先与这台电脑安全配对。授权只对当前项目有效。"}</p>
        <div className="v2-bridge-status">
          <i className={available ? "is-online" : undefined} />
          {available === null ? "正在检查连接服务…" : available ? "连接服务可用" : "连接服务未启动"}
        </div>
        {lease ? (
          <div className="v2-bridge-lease">
            <strong>已连接项目 {lease.projectId}</strong>
            <span>授权至 {new Date(lease.expiresAt).toLocaleTimeString()}</span>
            <button type="button" disabled={busy} onClick={() => void revoke()}>撤销本地授权</button>
          </div>
        ) : host === "tauri" ? (
          <div className="v2-bridge-form">
            <label>允许访问的网页地址<input value={origin} onChange={(event) => setOrigin(event.target.value)} /></label>
            <button type="button" disabled={busy || !projectId || !available} onClick={() => void start()}>创建 2 分钟连接码</button>
            {pairing && <div className="v2-bridge-code"><span>连接编号</span><code>{pairing.pairingId}</code><span>连接码</span><strong>{pairing.code}</strong></div>}
          </div>
        ) : (
          <div className="v2-bridge-form">
            <label>电脑端显示的连接编号<input value={pairingId} onChange={(event) => setPairingId(event.target.value)} /></label>
            <label>6 位连接码<input inputMode="numeric" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} /></label>
            <button type="button" disabled={busy || !available || !pairingId || code.length !== 6} onClick={() => void claim()}>连接当前项目</button>
          </div>
        )}
        {error && <p role="alert" className="v2-cad-message is-error">{error}</p>}
      </section>
    </div>
  );
}
