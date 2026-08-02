import {
  ExpertType,
  ExpertWorkspaceStatus,
  ProjectExpertStatus,
  type ExpertDefinition,
} from "@zhangwen/contracts";

export const THREE_EXPERT_TYPES: ExpertType[] = [
  ExpertType.PROBLEM_GUIDE,
  ExpertType.SMART_ENGINEER,
  ExpertType.STRUCTURE_ENGINEER,
];

export const DEFAULT_THREE_EXPERT_DEFINITIONS: ExpertDefinition[] = [
  {
    id: "expert_def_problem_guide",
    type: ExpertType.PROBLEM_GUIDE,
    name: "问题引导师",
    description: "澄清问题、需求、项目方案和教学目标",
    icon: "spark",
    builtIn: true,
    skillIds: ["idea-understanding", "requirement-clarification", "experiment-design"],
    supportedArtifactTypes: ["requirements", "project_brief", "lesson_plan"],
  },
  {
    id: "expert_def_smart_engineer",
    type: ExpertType.SMART_ENGINEER,
    name: "智能工程师",
    description: "硬件、软件、IoT、数据与 AI 部署",
    icon: "cpu",
    builtIn: true,
    skillIds: ["hardware-selection", "micropython-generation", "iot-mqtt"],
    supportedArtifactTypes: ["hardware_solution", "bom", "io_map", "micropython_project"],
  },
  {
    id: "expert_def_structure_engineer",
    type: ExpertType.STRUCTURE_ENGINEER,
    name: "结构工程师",
    description: "结构和外壳",
    icon: "box",
    builtIn: true,
    skillIds: ["dimension-reading", "parametric-modeling", "assembly-check"],
    supportedArtifactTypes: ["cad_model", "assembly", "print_settings"],
  },
];

export const EXPERT_WORKSPACE_STATUS_LABELS: Record<ExpertWorkspaceStatus, string> = {
  [ExpertWorkspaceStatus.NOT_STARTED]: "未开始",
  [ExpertWorkspaceStatus.WAITING_DEPENDENCY]: "等待依赖",
  [ExpertWorkspaceStatus.IN_PROGRESS]: "进行中",
  [ExpertWorkspaceStatus.AWAITING_USER]: "待用户确认",
  [ExpertWorkspaceStatus.COMPLETED]: "已完成",
  [ExpertWorkspaceStatus.OUTDATED]: "产物已过期",
};

export const EXPERT_POSITIONING: Record<string, string> = {
  problem_guide: "澄清问题、目标、约束和可执行路径",
  smart_engineer: "用硬件、软件、IoT 和 AI 能力实现想法",
  structure_engineer: "处理外壳、结构、装配和制造约束",
};

const PROJECT_STATUS_TO_WORKSPACE_STATUS: Record<ProjectExpertStatus, ExpertWorkspaceStatus> = {
  [ProjectExpertStatus.IDLE]: ExpertWorkspaceStatus.NOT_STARTED,
  [ProjectExpertStatus.WAITING_USER]: ExpertWorkspaceStatus.AWAITING_USER,
  [ProjectExpertStatus.WORKING]: ExpertWorkspaceStatus.IN_PROGRESS,
  [ProjectExpertStatus.BLOCKED]: ExpertWorkspaceStatus.WAITING_DEPENDENCY,
  [ProjectExpertStatus.COMPLETED]: ExpertWorkspaceStatus.COMPLETED,
};

const EXPERT_DISPLAY_NAMES: Record<string, string> = {
  problem_guide: "问题引导师",
  smart_engineer: "智能工程师",
  structure_engineer: "结构工程师",
  question_guide: "问题引导师",
  intelligent_engineer: "智能工程师",
  ideator: "问题引导师",
  educator: "问题引导师",
  open_hardware_designer: "智能工程师",
  structure_designer: "结构工程师",
  three_d_structure_designer: "结构工程师",
};

export function isThreeExpertType(
  expert: ExpertType | string | undefined | null
): expert is ExpertType {
  return THREE_EXPERT_TYPES.includes(expert as ExpertType);
}

export function getExpertDisplayName(
  expertType: ExpertType | string | undefined | null,
  fallback?: string | null
): string {
  if (expertType && EXPERT_DISPLAY_NAMES[expertType]) {
    return EXPERT_DISPLAY_NAMES[expertType];
  }
  return fallback ?? expertType ?? "未标记";
}

export function projectStatusToWorkspaceStatus(
  status?: ProjectExpertStatus | string | null,
): ExpertWorkspaceStatus {
  if (!status) return ExpertWorkspaceStatus.NOT_STARTED;
  return PROJECT_STATUS_TO_WORKSPACE_STATUS[status as ProjectExpertStatus]
    ?? ExpertWorkspaceStatus.NOT_STARTED;
}

export function getExpertWorkspaceStatusLabel(
  workspaceStatus?: string | null,
  projectStatus?: string | null
): string {
  const normalized = workspaceStatus ?? projectStatusToWorkspaceStatus(projectStatus);
  return EXPERT_WORKSPACE_STATUS_LABELS[normalized as ExpertWorkspaceStatus]
    ?? normalized
    ?? "未开始";
}
