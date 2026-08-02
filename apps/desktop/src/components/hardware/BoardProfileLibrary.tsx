import { useCallback, useEffect, useState } from "react";
import type { BoardProfile, BoardProfileSummary } from "@zhangwen/contracts";
import {
  getBoardProfile,
  listBoardProfiles,
  resetBoardProfile,
  updateBoardProfile,
} from "../../services/hardwareApi";

export function BoardProfileLibrary() {
  const [profiles, setProfiles] = useState<BoardProfileSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [profile, setProfile] = useState<BoardProfile | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dirty = profile !== null && draft !== profile.content;

  const loadDetail = useCallback(async (profileId: string) => {
    setLoading(true);
    setError(null);
    setStatus(null);
    setConfirmReset(false);
    try {
      const response = await getBoardProfile(profileId);
      setProfile(response.profile);
      setDraft(response.profile.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载开发板档案失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    void listBoardProfiles()
      .then((response) => {
        if (canceled) return;
        setProfiles(response.profiles);
        const firstId = response.profiles[0]?.id ?? null;
        setSelectedId(firstId);
        if (firstId) void loadDetail(firstId);
      })
      .catch((err: unknown) => {
        if (!canceled) {
          setError(err instanceof Error ? err.message : "加载开发板档案失败。");
          setLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [loadDetail]);

  const selectProfile = (profileId: string) => {
    if (dirty && !window.confirm("当前 Markdown 尚未保存，确定切换开发板吗？")) return;
    setSelectedId(profileId);
    void loadDetail(profileId);
  };

  const save = async () => {
    if (!profile || !dirty) return;
    setSaving(true);
    setError(null);
    try {
      const response = await updateBoardProfile(profile.id, {
        content: draft,
        expectedRevision: profile.revision,
      });
      setProfile(response.profile);
      setDraft(response.profile.content);
      setStatus("已保存 BoardProfile，下一次匹配该开发板时生效。");
      setProfiles((current) =>
        current.map((item) =>
          item.id === response.profile.id ? response.profile : item,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存开发板档案失败。");
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!profile) return;
    setSaving(true);
    setError(null);
    try {
      const response = await resetBoardProfile(profile.id, {
        expectedRevision: profile.revision,
      });
      setProfile(response.profile);
      setDraft(response.profile.content);
      setConfirmReset(false);
      setStatus("已恢复内置 BoardProfile。");
      setProfiles((current) =>
        current.map((item) =>
          item.id === response.profile.id ? response.profile : item,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复开发板档案失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="board-profile-library" aria-label="开发板档案">
      <nav className="board-profile-list" aria-label="开发板列表">
        {profiles.map((item) => (
          <button
            key={item.id}
            type="button"
            className={item.id === selectedId ? "is-selected" : ""}
            aria-pressed={item.id === selectedId}
            onClick={() => selectProfile(item.id)}
          >
            <strong>{item.displayName}</strong>
            <span>{item.platform}</span>
            <small>{item.overridden ? "已自定义" : "内置档案"}</small>
          </button>
        ))}
      </nav>

      {loading && !profile && <p className="sidebar-placeholder">加载中...</p>}
      {profile && (
        <div className="board-profile-editor">
          <header>
            <div>
              <strong>{profile.displayName}</strong>
              <span>{profile.id} · 版本 {profile.revision.slice(0, 8)}</span>
            </div>
            <span className="board-profile-source">
              {profile.overridden ? "自定义覆盖" : "内置默认"}
            </span>
          </header>
          {profile.skillPackage && (
            <section className="board-profile-skill" aria-label="已绑定 K10 Skill">
              <div>
                <strong>{profile.skillPackage.name}</strong>
                <span>版本 {profile.skillPackage.version} · 已绑定</span>
              </div>
              <p>
                {profile.skillPackage.referenceCount} 个参考 · {profile.skillPackage.templateCount} 个模板
                {profile.skillPackage.exampleCount > 0
                  ? ` · ${profile.skillPackage.exampleCount} 个示例`
                  : ""}
              </p>
              <small>
                {profile.skillPackage.syntaxValidated ? "语法已验证" : "语法尚未验证"}
                {" · "}
                {profile.skillPackage.hardwareValidated ? "已上板验证" : "尚未上板验证"}
              </small>
            </section>
          )}
          <textarea
            aria-label={`编辑 ${profile.displayName} BoardProfile`}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setStatus(null);
            }}
            spellCheck={false}
          />
          <div className="board-profile-actions">
            <button type="button" disabled={!dirty || saving} onClick={() => setDraft(profile.content)}>
              放弃修改
            </button>
            {confirmReset ? (
              <>
                <span>恢复后删除当前覆盖。</span>
                <button type="button" disabled={saving} onClick={() => setConfirmReset(false)}>
                  取消
                </button>
                <button type="button" disabled={saving} onClick={() => void reset()}>
                  确认恢复
                </button>
              </>
            ) : (
              <button
                type="button"
                disabled={!profile.overridden || saving}
                onClick={() => setConfirmReset(true)}
              >
                恢复默认
              </button>
            )}
            <button type="button" disabled={!dirty || saving} onClick={() => void save()}>
              {saving ? "保存中..." : "保存档案"}
            </button>
          </div>
        </div>
      )}
      {status && <p className="hardware-success" role="status">{status}</p>}
      {error && <p className="hardware-error" role="alert">{error}</p>}
    </section>
  );
}
