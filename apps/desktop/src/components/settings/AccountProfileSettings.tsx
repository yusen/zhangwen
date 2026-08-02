import { useEffect, useState } from "react";
import {
  BudgetPreference,
  TechnicalLevel,
  UserPersona,
  type AccountProfile,
} from "@zhangwen/contracts";
import { getAccountProfile, updateAccountProfile } from "../../services/authApi";
import { ProfileFields } from "../auth/ProfileFields";

const DEFAULT_PROFILE: AccountProfile = {
  persona: UserPersona.MAKER,
  technicalLevel: TechnicalLevel.BEGINNER,
  preferredBoards: [],
  budgetPreference: BudgetPreference.BALANCED,
  needsLesson: false,
  completed: true,
};

export function AccountProfileSettings() {
  const [profile, setProfile] = useState<AccountProfile>(DEFAULT_PROFILE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void getAccountProfile()
      .then((response) => {
        if (!active) return;
        setProfile({ ...DEFAULT_PROFILE, ...response.profile, completed: true });
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "暂时无法读取使用偏好。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const response = await updateAccountProfile({ ...profile, completed: true });
      setProfile({ ...DEFAULT_PROFILE, ...response.profile, completed: true });
      setMessage("使用偏好已保存，后续推荐将使用新设置。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-profile" aria-labelledby="settings-profile-title">
      <header className="settings-section-header">
        <span>账号资料</span>
        <h3 id="settings-profile-title">使用偏好</h3>
        <p>这些信息只用于改善方案、硬件和教学内容推荐，不会改变权限或设备安全规则。</p>
      </header>
      {loading ? (
        <p className="settings-profile-state" role="status">正在读取使用偏好…</p>
      ) : (
        <div className="settings-profile-form">
          <ProfileFields profile={profile} onChange={setProfile} busy={saving} />
          <div className="settings-profile-actions">
            <button type="button" disabled={saving} onClick={() => void save()}>
              {saving ? "保存中…" : "保存使用偏好"}
            </button>
            {message && <span role="status">{message}</span>}
          </div>
        </div>
      )}
      {error && <p className="settings-profile-error" role="alert">{error}</p>}
    </section>
  );
}
