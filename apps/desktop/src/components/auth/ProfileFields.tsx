import {
  BudgetPreference,
  TechnicalLevel,
  UserPersona,
  type AccountProfile,
} from "@zhangwen/contracts";
import type { Dispatch, SetStateAction } from "react";

interface ProfileFieldsProps {
  profile: AccountProfile;
  onChange: Dispatch<SetStateAction<AccountProfile>>;
  busy: boolean;
}

export function ProfileFields({ profile, onChange, busy }: ProfileFieldsProps) {
  return (
    <>
      <label>
        <span>你的身份</span>
        <select
          aria-label="你的身份"
          value={profile.persona}
          disabled={busy}
          onChange={(event) => onChange((current) => ({
            ...current,
            persona: event.target.value as AccountProfile["persona"],
            needsLesson: event.target.value === UserPersona.TEACHER
              ? current.needsLesson
              : false,
          }))}
        >
          <option value={UserPersona.TEACHER}>教师</option>
          <option value={UserPersona.STUDENT}>学生</option>
          <option value={UserPersona.ENGINEER}>工程师</option>
          <option value={UserPersona.MAKER}>创客</option>
          <option value={UserPersona.OTHER}>其他</option>
        </select>
      </label>
      <label>
        <span>技术水平</span>
        <select
          aria-label="技术水平"
          value={profile.technicalLevel}
          disabled={busy}
          onChange={(event) => onChange((current) => ({
            ...current,
            technicalLevel: event.target.value as AccountProfile["technicalLevel"],
          }))}
        >
          <option value={TechnicalLevel.BEGINNER}>入门</option>
          <option value={TechnicalLevel.INTERMEDIATE}>有一定经验</option>
          <option value={TechnicalLevel.ADVANCED}>熟练</option>
        </select>
      </label>
      <label>
        <span>常用板卡</span>
        <input
          aria-label="常用板卡"
          value={profile.preferredBoards.join("、")}
          disabled={busy}
          onChange={(event) => onChange((current) => ({
            ...current,
            preferredBoards: event.target.value
              .split(/[、,，]/)
              .map((item) => item.trim())
              .filter(Boolean)
              .slice(0, 12),
          }))}
        />
      </label>
      <label>
        <span>预算倾向</span>
        <select
          aria-label="预算倾向"
          value={profile.budgetPreference}
          disabled={busy}
          onChange={(event) => onChange((current) => ({
            ...current,
            budgetPreference: event.target.value as AccountProfile["budgetPreference"],
          }))}
        >
          <option value={BudgetPreference.ECONOMY}>经济优先</option>
          <option value={BudgetPreference.BALANCED}>均衡</option>
          <option value={BudgetPreference.PERFORMANCE}>性能优先</option>
        </select>
      </label>
      {profile.persona === UserPersona.TEACHER && (
        <label className="auth-profile-checkbox">
          <input
            type="checkbox"
            checked={profile.needsLesson}
            disabled={busy}
            onChange={(event) => onChange((current) => ({
              ...current,
              needsLesson: event.target.checked,
            }))}
          />
          <span>项目默认包含教学内容</span>
        </label>
      )}
    </>
  );
}
