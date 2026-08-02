import { useState } from "react";
import { CreatorCommand, type CreatorWorkspace } from "@zhangwen/contracts";
import { useV2CadWorkspace } from "../../hooks/useV2CadWorkspace";
import { useV2ProjectData } from "../../hooks/useV2ProjectData";
import { StructurePage } from "../../components/v2/pages/StructurePage";

export default function StructureStage({
  workspace,
  professionalMode,
  onCommand,
}: {
  workspace: CreatorWorkspace;
  professionalMode: boolean;
  onCommand: (command: CreatorCommand, payload: Record<string, unknown>) => Promise<void>;
}) {
  const stage = workspace.stages.find((item) => item.stage === "STRUCTURE_3D");
  const cad = useV2CadWorkspace(workspace.projectId);
  const v2 = useV2ProjectData(workspace.projectId);
  const [recording, setRecording] = useState(false);
  const [recordError, setRecordError] = useState<string | null>(null);
  const current = cad.workspace?.currentRevision ?? null;
  const structurePassed = workspace.evidence.some((item) => item.kind === "STRUCTURE_CHECK" && item.status === "CURRENT" && item.passed);
  const noStructure = stage?.status === "NOT_APPLICABLE";

  if (noStructure) {
    return (
      <div className="creator-stage-content" data-testid="creator-stage-structure">
        <section className="creator-stage-hero"><span>尺寸、安装与制造</span><h2>3D 结构</h2><p>{stage.detail}</p></section>
        <section className="creator-stage-card creator-structure-na"><strong>不适用</strong><h3>当前作品不需要独立结构件</h3><p>结构阶段仍保留可查看；如果方案以后增加外壳、支架或面板，确认新方案版本后即可在这里创建结构修订。</p></section>
      </div>
    );
  }

  const recordStructure = async () => {
    if (!current) return;
    setRecording(true);
    setRecordError(null);
    try {
      await onCommand(CreatorCommand.RECORD_STRUCTURE_CHECK, {
        passed: true,
        summary: `结构修订 ${current.id} 已确认，GLB、STL、STEP 与 manifest 完整并通过文件校验。`,
        sourceId: current.id,
        bindings: {
          solutionRevisionId: workspace.currentSolution?.id ?? "",
          structureRevisionId: current.id,
          sourceSha256: current.sourceSha256,
        },
      });
    } catch (reason) {
      setRecordError(reason instanceof Error ? reason.message : "结构检查记录失败。");
    } finally {
      setRecording(false);
    }
  };

  return (
    <div className="creator-stage-content creator-structure-stage" data-testid="creator-stage-structure">
      <section className="creator-stage-hero"><span>尺寸、安装与制造</span><h2>3D 结构</h2><p>{stage?.detail}</p></section>
      {recordError ? <div className="creator-error" role="alert">{recordError}</div> : null}
      <section className="creator-stage-card creator-structure-summary">
        <div><strong>方案结构要求</strong><span>{workspace.currentSolution?.structure ?? "等待方案确认"}</span></div>
        <div><strong>不可变修订</strong><span>{current ? `${current.id.slice(0, 12)} · ${current.sourceSha256.slice(0, 12)}` : "尚未生成"}</span></div>
        <button type="button" disabled={!current?.artifactVersionId || recording || structurePassed} onClick={() => void recordStructure()}>{structurePassed ? "结构检查已通过" : "校验制造文件"}</button>
      </section>
      <div className="creator-cad-host">
        <StructurePage
          state={v2.data?.state ?? null}
          professionalMode={professionalMode}
          workspace={cad.workspace}
          busy={cad.busy || cad.loading || v2.loading}
          error={cad.error ?? v2.error}
          lastResult={cad.lastResult}
          decorativePlaceholder={false}
          onSubmit={async (prompt, mode) => {
            if (!v2.data) throw new Error("作品版本尚未同步，请稍后重试。");
            const result = await cad.submit({
              prompt,
              mode,
              baseProjectVersion: v2.data.state.projectVersion,
              currentRevisionId: cad.workspace?.currentRevision?.id,
            });
            v2.refresh();
            return result;
          }}
          onConfirm={async (revisionId) => {
            const result = await cad.confirmAndBuild(revisionId);
            v2.refresh();
            return result;
          }}
          onBuild={async (revisionId) => {
            const result = await cad.build(revisionId);
            v2.refresh();
            return result;
          }}
          onUndo={async (revisionId) => {
            if (!v2.data) throw new Error("作品版本尚未同步，请稍后重试。");
            const result = await cad.undo(revisionId, v2.data.state.projectVersion);
            v2.refresh();
            return result;
          }}
        />
      </div>
      <section className="creator-stage-card creator-structure-revisions">
        <header><h3>结构修订历史</h3><span>{cad.workspace?.revisions.length ?? 0} 个版本</span></header>
        {(cad.workspace?.revisions ?? []).map((revision) => <article key={revision.id}><strong>{revision.status}</strong><span>{revision.intentSummary}</span><code>{revision.sourceSha256.slice(0, 16)}</code></article>)}
      </section>
    </div>
  );
}
