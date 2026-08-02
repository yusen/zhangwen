import { useCallback, useEffect, useState } from "react";
import type {
  HardwareComponent,
  MechanicalProfileSummary,
} from "@zhangwen/contracts";
import {
  confirmMechanicalProfileLink,
  generateMechanicalProfilePreview,
  listHardware,
  listMechanicalProfiles,
  removeMechanicalProfileLink,
} from "../../services/hardwareApi";
import { subscribeHardwareSkillUpdated } from "../../utils/hardwareSkillEvents";

const MOUNTING_STRATEGY_LABELS: Record<
  MechanicalProfileSummary["mountingStrategy"],
  string
> = {
  none: "无专用固定",
  hole_fastened: "螺孔固定",
  edge_retainer: "边缘限位",
};

const SURFACE_LABELS: Record<string, string> = {
  base_floor: "底壳内底面",
  lid_inner: "上盖内侧",
  lid_outer: "上盖外侧",
  front_inner: "前壁内侧",
  back_inner: "后壁内侧",
  left_inner: "左壁内侧",
  right_inner: "右壁内侧",
  external: "壳体外部",
};

const EVIDENCE_LABELS: Record<MechanicalProfileSummary["evidenceLevel"], string> = {
  TRUSTED: "可信内置档案",
  CONFIRMED: "已确认档案",
};

const REPRESENTATION_LABELS: Record<MechanicalProfileSummary["representation"], string> = {
  parametric_envelope: "参数化包络",
  envelope_only: "仅包络",
};

interface MechanicalProfileLibraryProps {
  onOpenPreview?: (profile: MechanicalProfileSummary) => void;
}

export function MechanicalProfileLibrary({ onOpenPreview }: MechanicalProfileLibraryProps) {
  const [profiles, setProfiles] = useState<MechanicalProfileSummary[]>([]);
  const [hardware, setHardware] = useState<HardwareComponent[]>([]);
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lockedHardwareIds = new Set(
    profiles.flatMap((profile) => profile.lockedHardwareIds),
  );

  const load = useCallback(async (clearStatus = true) => {
    setLoading(true);
    setError(null);
    if (clearStatus) setStatus(null);
    try {
      const [profileResponse, hardwareResponse] = await Promise.all([
        listMechanicalProfiles(),
        listHardware(),
      ]);
      setProfiles(profileResponse.profiles);
      setHardware(hardwareResponse.components);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载机械档案失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(
    () => subscribeHardwareSkillUpdated(() => {
      void load(false);
    }),
    [load],
  );

  const confirmLink = async (profile: MechanicalProfileSummary) => {
    const hardwareId = selections[profile.profileId];
    if (!hardwareId) return;
    const key = `link:${profile.profileId}`;
    setActionKey(key);
    setError(null);
    setStatus(null);
    try {
      await confirmMechanicalProfileLink(hardwareId, {
        profileId: profile.profileId,
        revision: profile.revision,
      });
      setSelections((current) => ({ ...current, [profile.profileId]: "" }));
      setStatus(`已将 ${hardwareName(hardware, hardwareId)} 关联到 ${profile.displayName}。`);
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "关联机械档案失败。");
    } finally {
      setActionKey(null);
    }
  };

  const removeLink = async (profile: MechanicalProfileSummary, hardwareId: string) => {
    if (profile.lockedHardwareIds.includes(hardwareId)) return;
    const key = `unlink:${hardwareId}`;
    setActionKey(key);
    setError(null);
    setStatus(null);
    try {
      await removeMechanicalProfileLink(hardwareId);
      setStatus(`已解除 ${hardwareName(hardware, hardwareId)} 的机械档案关联。`);
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "解除机械档案关联失败。");
    } finally {
      setActionKey(null);
    }
  };

  const openPreview = async (profile: MechanicalProfileSummary) => {
    const key = `preview:${profile.profileId}`;
    setActionKey(key);
    setError(null);
    setStatus("正在根据 mechanical.md 的自然语言描述生成 3D 预览...");
    try {
      const response = await generateMechanicalProfilePreview(profile.profileId, {
        revision: profile.revision,
      });
      setProfiles((current) => current.map((item) => (
        item.profileId === profile.profileId ? response.profile : item
      )));
      setStatus(response.generationSource === "ENVELOPE_FALLBACK"
        ? "该档案没有 Hardware Skill 自然描述，已打开仅包络预览。"
        : "3D 预览已与当前 mechanical.md 自然描述同步。");
      onOpenPreview?.(response.profile);
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "根据自然描述生成 3D 预览失败。");
    } finally {
      setActionKey(null);
    }
  };

  return (
    <section className="mechanical-profile-library" aria-label="机械档案">
      <header className="mechanical-profile-toolbar">
        <div>
          <strong>受信任机械档案</strong>
          <span>结构工程师仅使用已确认的精确版本和校验值。</span>
        </div>
        <button
          type="button"
          className="mechanical-profile-refresh"
          onClick={() => void load()}
          disabled={loading || actionKey !== null}
        >
          刷新
        </button>
      </header>

      {error && <p className="hardware-error" role="alert">{error}</p>}
      {status && <p className="hardware-success" role="status">{status}</p>}
      {loading && !loaded && <p className="sidebar-placeholder">加载机械档案...</p>}
      {!loading && loaded && profiles.length === 0 && (
        <p className="sidebar-placeholder">暂无可用机械档案。</p>
      )}

      {loaded && profiles.length > 0 && (
        <div className="mechanical-profile-grid">
          {profiles.map((profile) => (
            <article
              key={`${profile.profileId}:${profile.revision}`}
              className="mechanical-profile-item"
              aria-label={profile.displayName}
            >
              <header>
                <div>
                  <strong>{profile.displayName}</strong>
                  <span>{profile.profileId} · 版本 {profile.revision}</span>
                </div>
                <span className="mechanical-profile-evidence">
                  {EVIDENCE_LABELS[profile.evidenceLevel]}
                </span>
              </header>

              <dl className="mechanical-profile-facts">
                <div>
                  <dt>外形尺寸</dt>
                  <dd>{formatDimensions(profile)} mm</dd>
                </div>
                <div>
                  <dt>安装策略</dt>
                  <dd>{MOUNTING_STRATEGY_LABELS[profile.mountingStrategy]}</dd>
                </div>
                <div>
                  <dt>首选安装面</dt>
                  <dd>{surfaceLabel(profile.preferredSurface)}</dd>
                </div>
                <div>
                  <dt>允许安装面</dt>
                  <dd>{profile.allowedSurfaces.map(surfaceLabel).join("、") || "无"}</dd>
                </div>
                <div>
                  <dt>边界间隙</dt>
                  <dd>{formatNumber(profile.clearance)} mm</dd>
                </div>
                <div>
                  <dt>几何证据</dt>
                  <dd>{EVIDENCE_LABELS[profile.evidenceLevel]} · {REPRESENTATION_LABELS[profile.representation]}</dd>
                </div>
              </dl>

              <div className="mechanical-profile-actions">
                <button
                  type="button"
                  aria-label={`查看 ${profile.displayName} 3D 预览`}
                  disabled={actionKey !== null}
                  onClick={() => void openPreview(profile)}
                >
                  {actionKey === `preview:${profile.profileId}`
                    ? "生成预览中..."
                    : "查看 3D 预览"}
                </button>
                <span>从 mechanical.md 自然描述生成；声明式几何仅作可重建缓存</span>
              </div>

              <div className="mechanical-profile-hash">
                <span>SHA-256</span>
                <code title={profile.contentSha256}>{profile.contentSha256.slice(0, 12)}</code>
              </div>

              <section className="mechanical-profile-links" aria-label={`${profile.displayName} 已关联硬件`}>
                <strong>已关联硬件</strong>
                {profile.confirmedHardwareIds.length === 0 ? (
                  <span className="mechanical-profile-empty">尚未关联</span>
                ) : (
                  <ul>
                    {profile.confirmedHardwareIds.map((hardwareId) => {
                      const locked = profile.lockedHardwareIds.includes(hardwareId);
                      const unlinking = actionKey === `unlink:${hardwareId}`;
                      return (
                        <li key={hardwareId}>
                          <span>{hardwareName(hardware, hardwareId)}</span>
                          {locked && <small>内置锁定</small>}
                          <button
                            type="button"
                            aria-label={`解除 ${hardwareName(hardware, hardwareId)} 与 ${profile.displayName} 的关联`}
                            title={locked ? "内置映射不可解除" : "解除关联"}
                            disabled={locked || actionKey !== null}
                            onClick={() => void removeLink(profile, hardwareId)}
                          >
                            {unlinking ? "解除中..." : "解除"}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>

              <div className="mechanical-profile-link-form">
                <label htmlFor={`mechanical-profile-hardware-${profile.profileId}`}>
                  选择关联硬件
                </label>
                <div>
                  <select
                    id={`mechanical-profile-hardware-${profile.profileId}`}
                    aria-label={`选择关联到 ${profile.displayName} 的硬件`}
                    value={selections[profile.profileId] ?? ""}
                    disabled={hardware.length === 0 || actionKey !== null}
                    onChange={(event) =>
                      setSelections((current) => ({
                        ...current,
                        [profile.profileId]: event.target.value,
                      }))
                    }
                  >
                    <option value="">请选择硬件</option>
                    {hardware.filter((component) => !lockedHardwareIds.has(component.id)).map((component) => (
                      <option key={component.id} value={component.id}>
                        {component.name} ({component.id})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!selections[profile.profileId] || actionKey !== null}
                    onClick={() => void confirmLink(profile)}
                  >
                    {actionKey === `link:${profile.profileId}` ? "关联中..." : "确认关联"}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function formatDimensions(profile: MechanicalProfileSummary): string {
  const { length_x, width_y, height_z } = profile.dimensions;
  return `${formatNumber(length_x)} x ${formatNumber(width_y)} x ${formatNumber(height_z)}`;
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
}

function surfaceLabel(surface: string): string {
  return SURFACE_LABELS[surface] ?? surface;
}

function hardwareName(hardware: HardwareComponent[], hardwareId: string): string {
  const component = hardware.find((item) => item.id === hardwareId);
  return component ? `${component.name} (${hardwareId})` : hardwareId;
}
