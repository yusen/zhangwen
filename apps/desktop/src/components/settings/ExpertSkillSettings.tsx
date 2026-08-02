import { useEffect, useMemo, useState } from "react";
import type { AgentPackageSummary, SkillDefinition } from "@zhangwen/contracts";
import { listAgentPackages, listSkills, updateSkill } from "../../services/projectsApi";

interface ExpertSkillSettingsProps {
  onOpenPackage?: (agentPackage: AgentPackageSummary) => void;
}

export function ExpertSkillSettings({ onOpenPackage }: ExpertSkillSettingsProps) {
  const [packages, setPackages] = useState<AgentPackageSummary[]>([]);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingSkillId, setSavingSkillId] = useState<string | null>(null);
  const [editingSkillId, setEditingSkillId] = useState<string | null>(null);
  const [skillDescription, setSkillDescription] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    void Promise.all([listAgentPackages(), listSkills()])
      .then(([packageResponse, skillResponse]) => {
        if (canceled) return;
        setPackages(packageResponse.packages);
        setSkills(skillResponse.skills);
        setError(null);
      })
      .catch((loadError) => {
        if (!canceled) {
          setError(loadError instanceof Error ? loadError.message : "智能体行为项目暂时不可用。");
        }
      })
      .finally(() => {
        if (!canceled) setLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, []);

  const boundSkills = useMemo(() => {
    const boundIds = new Set(packages.flatMap((agentPackage) => agentPackage.skillIds));
    return skills.filter((skill) => boundIds.has(skill.id));
  }, [packages, skills]);

  const skillOwners = useMemo(() => {
    const owners = new Map<string, string[]>();
    for (const agentPackage of packages) {
      for (const skillId of agentPackage.skillIds) {
        owners.set(skillId, [...(owners.get(skillId) ?? []), agentPackage.displayName]);
      }
    }
    return owners;
  }, [packages]);

  const saveSkillDescription = async (skill: SkillDefinition) => {
    const nextDescription = skillDescription.trim();
    if (!nextDescription) return;
    setSavingSkillId(skill.id);
    setError(null);
    setFeedback(null);
    try {
      const response = await updateSkill(skill.id, { description: nextDescription });
      setSkills((current) => current.map((item) =>
        item.id === skill.id ? response.skill : item
      ));
      setEditingSkillId(null);
      setFeedback(`已保存“${skill.name}”的执行能力描述。`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存执行能力描述失败。");
    } finally {
      setSavingSkillId(null);
    }
  };

  return (
    <section className="agent-package-settings" aria-label="智能体配置">
      <header>
        <span>专业模式</span>
        <h3>三位工程师行为项目</h3>
        <p>确认和修改入口：设置 → 智能体 → 打开行为项目。保存后从目标工程师的下一次回复开始生效。</p>
      </header>

      <div className="agent-package-boundary" role="note">
        <strong>Markdown 只定义行为规则</strong>
        <span>工程师身份、受控 Skill、文件权限和 Tool Runner 边界由系统 manifest 锁定。</span>
      </div>

      {loading && packages.length === 0 && (
        <p className="settings-empty" role="status">正在读取工程师行为项目...</p>
      )}
      {error && <p className="settings-feedback settings-feedback-error" role="alert">{error}</p>}

      <div className="agent-package-grid">
        {packages.map((agentPackage) => (
          <article key={agentPackage.expertType} className="agent-package-card">
            <header>
              <div className="agent-package-avatar" aria-hidden="true">
                {agentPackage.displayName.slice(0, 1)}
              </div>
              <div>
                <h4>{agentPackage.displayName}</h4>
                <span>{agentPackage.overridden ? "使用自定义 Markdown" : "使用内置 Markdown"}</span>
              </div>
            </header>
            <p>{agentPackage.description}</p>
            <dl>
              <div><dt>入口</dt><dd>{agentPackage.entryFile}</dd></div>
              <div><dt>文档</dt><dd>{agentPackage.fileCount} 个 Markdown 文件</dd></div>
              <div><dt>受控能力</dt><dd>{agentPackage.skillIds.length} 项</dd></div>
            </dl>
            {agentPackage.capabilityBoundaries.length > 0 && (
              <p className="agent-package-capability">
                安全边界：{agentPackage.capabilityBoundaries.join("；")}
              </p>
            )}
            {agentPackage.validationIssues.map((issue) => (
              <p key={`${issue.path}:${issue.message}`} className="settings-feedback settings-feedback-error" role="alert">
                {issue.path}：{issue.message}
              </p>
            ))}
            <button
              type="button"
              disabled={!onOpenPackage}
              aria-label={`打开 ${agentPackage.displayName}行为项目`}
              onClick={() => onOpenPackage?.(agentPackage)}
            >
              打开行为项目
            </button>
          </article>
        ))}
      </div>

      <section className="agent-capability-list" aria-label="受控执行能力">
        <header>
          <div>
            <h4>执行能力</h4>
            <p>这里仍是 Registry Skill 的受控描述；它与上方 Markdown 行为项目分离，权限和风险等级由系统锁定。</p>
          </div>
          <span>{boundSkills.length} 项已绑定能力</span>
        </header>
        {boundSkills.map((skill) => (
          <article key={skill.id} className="agent-capability-row">
            <div>
              <strong>{skill.name}</strong>
              <span>
                {(skillOwners.get(skill.id) ?? []).join("、") || "未绑定"} · {skill.enabled ? "已启用" : "已停用"}
              </span>
            </div>
            {editingSkillId === skill.id ? (
              <>
                <textarea
                  aria-label={`Skill 描述 ${skill.name}`}
                  value={skillDescription}
                  maxLength={1000}
                  rows={3}
                  disabled={savingSkillId === skill.id}
                  onChange={(event) => setSkillDescription(event.target.value)}
                />
                <div className="settings-inline-actions">
                  <button
                    type="button"
                    disabled={savingSkillId === skill.id}
                    onClick={() => setEditingSkillId(null)}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    disabled={!skillDescription.trim() || savingSkillId === skill.id}
                    onClick={() => void saveSkillDescription(skill)}
                  >
                    {savingSkillId === skill.id ? "保存中..." : "保存描述"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p>{skill.description}</p>
                <button
                  type="button"
                  onClick={() => {
                    setEditingSkillId(skill.id);
                    setSkillDescription(skill.description);
                    setFeedback(null);
                  }}
                >
                  编辑描述
                </button>
              </>
            )}
          </article>
        ))}
      </section>

      {feedback && (
        <p className="settings-feedback settings-feedback-ok" role="status">{feedback}</p>
      )}
    </section>
  );
}
