import { useState } from "react";
import type { ChangeSet } from "@zhangwen/contracts";
import { commitV2ChangeSet, confirmV2ChangeSet } from "../../services/v2Api";

export function V2ChangeSetPanel({
  projectId,
  changeSets,
  professionalMode,
  onChanged,
}: {
  projectId: string;
  changeSets: ChangeSet[];
  professionalMode: boolean;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = changeSets.find((item) => ["READY", "CONFIRMED"].includes(item.status));
  if (!current) return null;

  const act = async (kind: "confirm" | "commit") => {
    setBusy(true);
    setError(null);
    try {
      if (kind === "confirm") await confirmV2ChangeSet(projectId, current.id);
      else await commitV2ChangeSet(projectId, current.id);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "修改操作失败。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="v2-changeset-panel" aria-label="待确认修改">
      <header>
        <span>{professionalMode ? "Change Set" : "待确认修改"}</span>
        <b data-status={current.status}>{statusLabel(current.status)}</b>
      </header>
      <strong>{current.intentSummary}</strong>
      <ul>
        {current.operations.slice(0, 5).map((operation, index) => (
          <li key={`${operation.op}-${operation.path}-${index}`}>
            <span>{operationLabel(operation.op)}</span>
            {professionalMode && <code>{operation.path}</code>}
            {professionalMode && operation.value !== undefined && <small>{JSON.stringify(operation.value)}</small>}
          </li>
        ))}
      </ul>
      <footer>
        <span>{professionalMode ? `风险：${riskLabel(current.riskLevel)}` : riskHelp(current.riskLevel)}</span>
        {current.status === "READY" && <button type="button" disabled={busy} onClick={() => void act("confirm")}>确认修改</button>}
        {current.status === "CONFIRMED" && <button type="button" disabled={busy} onClick={() => void act("commit")}>应用到项目</button>}
      </footer>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

function statusLabel(status: ChangeSet["status"]): string {
  return { DRAFT: "草稿", VALIDATING: "校验中", READY: "待确认", CONFIRMED: "已确认", COMMITTED: "已提交", REJECTED: "已拒绝", CANCELED: "已取消" }[status];
}

function operationLabel(operation: string): string {
  return ({
    SET_PROJECT_MODE: "更新项目设置",
    UPSERT_FACT: "更新项目信息",
    REMOVE_FACT: "移除项目信息",
    BIND_CAPABILITY: "补充实现能力",
    UNBIND_CAPABILITY: "移除实现能力",
    MARK_ARTIFACT_OUTDATED: "标记成果需要更新",
  } as Record<string, string>)[operation] ?? "更新项目内容";
}

function riskLabel(risk: ChangeSet["riskLevel"]): string {
  return { LOW: "低", MEDIUM: "中", HIGH: "高" }[risk];
}

function riskHelp(risk: ChangeSet["riskLevel"]): string {
  return {
    LOW: "不会直接操作设备",
    MEDIUM: "确认后会更新项目方案",
    HIGH: "请仔细核对后再确认",
  }[risk];
}
