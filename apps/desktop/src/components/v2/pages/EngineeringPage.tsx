import {
  ArtifactStatus,
  type ArtifactDefinition,
  type ProjectProgressSnapshot,
  type ProjectState,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import {
  ArtifactWorkspace,
  CodeUploadGuide,
  EngineeringPanel,
  preferredHardware,
} from "./common";

export type EngineeringWorkspaceView = "hardware" | "code" | "device" | "validation";

export function EngineeringPage({
  workspace: _workspace,
  state,
  artifacts,
  artifactsLoading,
  artifactsError,
  progress,
  progressLoading,
  progressError,
  professionalMode: _professionalMode,
  deviceRefreshRevision: _deviceRefreshRevision,
  section,
  onSectionChange,
  onOpenArtifact,
}: {
  workspace: ProjectWorkspace;
  state: ProjectState | null;
  artifacts: ArtifactDefinition[];
  artifactsLoading: boolean;
  artifactsError: string | null;
  progress: ProjectProgressSnapshot | null;
  progressLoading: boolean;
  progressError: string | null;
  professionalMode: boolean;
  deviceRefreshRevision: number;
  section: EngineeringWorkspaceView;
  onSectionChange: (view: EngineeringWorkspaceView) => void;
  onOpenArtifact: (artifactId: string, versionId?: string | null) => void;
}) {
  const hardware = preferredHardware(state);
  const codeArtifacts = artifacts.filter((item) => item.kind === "CODE");
  const hasAcceptedCode = codeArtifacts.some((item) => item.status === ArtifactStatus.APPROVED);
  return (
    <div className="v2-engineering-page">
      <nav className="v2-subnav" aria-label="工程实现二级导航">
        {([["hardware", "硬件"], ["code", "代码"], ["device", "设备"], ["validation", "验证"]] as const).map(([id, label]) => (
          <button key={id} type="button" aria-current={section === id ? "page" : undefined} onClick={() => onSectionChange(id)}>{label}</button>
        ))}
      </nav>
      {section === "hardware" && (
        <EngineeringPanel
          title="硬件与供电"
          lead="核对器件清单、供电方式和接线要求。"
          items={hardware.map((item) => `${item.name}${_professionalMode && item.skillName ? ` · ${item.skillName}` : ""}${_professionalMode && item.skillRevision ? ` · r${item.skillRevision}` : ""}`)}
          empty="项目尚未确认硬件；请返回对话说明需要的功能或器件。"
        />
      )}
      {section === "code" && (
        <>
          <ArtifactWorkspace
            title="项目代码"
            lead="查看代码内容，完成检查后再上传到设备。"
            artifacts={codeArtifacts}
            loading={artifactsLoading}
            error={artifactsError}
            empty="尚未生成项目代码。"
            onOpenArtifact={onOpenArtifact}
            professionalMode={_professionalMode}
          />
          {!!codeArtifacts.length && (
            <CodeUploadGuide
              hasAcceptedCode={hasAcceptedCode}
              onOpenDevice={() => onSectionChange("device")}
            />
          )}
        </>
      )}
      {section === "device" && (
        <EngineeringPanel
          title="连接与上传"
          lead="设备操作已放到右侧“设备”，主页面继续保留代码和验证上下文。"
          items={["先确认代码", "连接设备", "确认上传", "查看运行结果"]}
          empty="打开右侧“设备”开始连接。"
        />
      )}
      {section === "validation" && (
        <EngineeringPanel
          title="验证证据"
          lead="分别查看代码检查、模拟运行和真实设备测试结果。"
          items={progress?.readinessSummary.map((item) => `${item.label}：${item.message}`) ?? []}
          empty={progressLoading ? "正在读取验证状态…" : progressError ?? "尚未完成验证。"}
        />
      )}
    </div>
  );
}
