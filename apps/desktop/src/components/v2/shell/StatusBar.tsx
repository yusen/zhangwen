import { HealthIndicator } from "../../health/HealthIndicator";

interface StatusBarProps {
  healthStatus: "checking" | "ok" | "recovering" | "disconnected";
  providerText: string;
  runningJobs: number;
  professionalMode: boolean;
  onOpenJobs: () => void;
}

export function StatusBar({
  healthStatus,
  providerText,
  runningJobs,
  professionalMode,
  onOpenJobs,
}: StatusBarProps) {
  return (
    <footer className="zw-statusbar">
      <HealthIndicator status={healthStatus} />
      {professionalMode && <span>云端 LLM · {providerText}</span>}
      <span className="zw-spacer" />
      <button type="button" className="zw-jobs-pill" onClick={onOpenJobs}>
        {professionalMode
          ? <>本地任务 · <b>{runningJobs}</b> 个运行中</>
          : runningJobs
            ? <>正在处理 <b>{runningJobs}</b> 项</>
            : "暂无后台任务"}
      </button>
    </footer>
  );
}
