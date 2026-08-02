import type { ExpertType } from "@zhangwen/contracts";

export function stageLabel(stage: string): string {
  return ({
    IDEA: "创意",
    CLARIFYING: "澄清",
    SOLUTION_DRAFT: "方案草稿",
    SOLUTION_CONFIRMED: "方案已确认",
    PROPOSAL_DRAFT: "立项草稿",
    PROPOSAL_CONFIRMED: "立项已确认",
    EXECUTION_PLANNED: "执行计划",
    IMPLEMENTING: "实现中",
    VALIDATING: "验证中",
    READY_TO_UPLOAD: "可上传",
    DEVICE_VERIFIED: "设备已验证",
    READY_TO_PUBLISH: "可交付",
    PUBLISHED: "已发布",
  } as Record<string, string>)[stage] ?? stage;
}

export function expertTypeLabel(expertType?: ExpertType): string {
  return ({
    problem_guide: "问题引导师",
    smart_engineer: "智能工程师",
    structure_engineer: "结构工程师",
  } as Record<string, string>)[expertType ?? ""] ?? "按页面自动选择主责工程师";
}

export function providerLabel(provider?: string | null): string {
  if (!provider) return "未配置";
  return ({
    deepseek: "DeepSeek",
    qwen: "千问（Qwen）",
    glm: "智谱 GLM",
    kimi: "Kimi",
  } as Record<string, string>)[provider] ?? provider;
}

export function artifactKindLabel(kind: string): string {
  return ({
    DOCUMENT: "文档",
    CODE: "代码",
    IMAGE: "图片",
    MODEL_3D: "3D",
    DEVICE_LOG: "设备日志",
    PACKAGE: "项目包",
    REPORT: "报告",
  } as Record<string, string>)[kind] ?? kind;
}

export function artifactStatusLabel(status: string): string {
  return ({
    DRAFT: "草稿",
    GENERATING: "生成中",
    NEEDS_REVIEW: "待确认",
    APPROVED: "已确认",
    REJECTED: "已退回",
    STALE: "已过期",
    FAILED: "失败",
    ARCHIVED: "已归档",
  } as Record<string, string>)[status] ?? status;
}
