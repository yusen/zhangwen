import type { ExpertType } from "../domain/types";

export interface RouterOutput {
  intent: string;
  projectName: string;
  initialExpert: ExpertType;
  recommendedExperts: ExpertType[];
  confidence: number;
  reason: string;
  requiresClarification: boolean;
}

export interface EntryRouter {
  route(input: {
    text: string;
    userSelectedExpert?: ExpertType;
  }): Promise<RouterOutput>;
}

// 实现要求：
// 1. 用户指定专家时优先。
// 2. 模型输出必须使用 router-output.schema.json 校验。
// 3. 校验失败重试一次；再次失败使用规则降级。
// 4. 不向用户暴露内部 JSON 和推理过程。
// 5. 模糊或多领域未澄清需求默认 problem_guide。
