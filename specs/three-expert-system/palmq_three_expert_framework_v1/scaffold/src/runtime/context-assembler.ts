import type { ExpertType, ProjectSharedContext } from "../domain/types";

export interface ContextAssemblyInput {
  projectId: string;
  expert: ExpertType;
  taskId?: string;
  userMessage: string;
}

export interface AssembledContext {
  projectSummary: string;
  currentTask?: unknown;
  relevantFacts: unknown[];
  relevantDecisions: unknown[];
  upstreamArtifacts: unknown[];
  relevantDevices: unknown[];
  relevantConflicts: unknown[];
}

export interface ContextAssembler {
  assemble(input: ContextAssemblyInput): Promise<AssembledContext>;
}

// 不允许默认注入完整项目聊天。
// 应根据 expert、taskId、产物依赖和事实标签进行最小化检索。
