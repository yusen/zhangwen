import type { ExpertType } from "../domain/types";

export interface SkillDefinition {
  id: string;
  ownerExpert: ExpertType;
  name: string;
  inputSchemaKey: string;
  outputSchemaKey: string;
  requiredTools: string[];
  riskLevel: "low" | "medium" | "high";
  confirmationPolicy: "never" | "before_external_effect" | "always";
}

export const SMART_ENGINEER_SKILLS: SkillDefinition[] = [
  ["hardware-selection", "硬件选型", "hardware-selection.input", "hardware-selection.output", [], "low", "never"],
  ["bom-generation", "BOM生成", "bom.input", "bom.output", [], "low", "never"],
  ["io-map", "IO Map", "io-map.input", "io-map.output", [], "medium", "never"],
  ["wiring", "接线设计", "wiring.input", "wiring.output", [], "medium", "never"],
  ["electrical-check", "电气兼容检查", "electrical.input", "electrical.output", [], "high", "always"],
  ["micropython-generation", "MicroPython代码生成", "code.input", "code.output", ["filesystem"], "medium", "before_external_effect"],
  ["arduino-generation", "Arduino代码生成", "code.input", "code.output", ["filesystem"], "medium", "before_external_effect"],
  ["code-review", "代码审查", "review.input", "review.output", [], "low", "never"],
  ["mock-test", "Mock测试", "test.input", "test.output", ["sandbox"], "medium", "before_external_effect"],
  ["iot-mqtt", "MQTT配置", "mqtt.input", "mqtt.output", [], "medium", "never"],
  ["iot-http", "HTTP配置", "http.input", "http.output", [], "medium", "never"],
  ["data-acquisition", "数据采集", "data.input", "data.output", ["device"], "high", "always"],
  ["data-analysis", "数据分析", "analysis.input", "analysis.output", ["sandbox"], "low", "never"],
  ["ai-deployment", "AI模型部署", "ai.input", "ai.output", ["filesystem"], "medium", "before_external_effect"],
  ["vision-inference", "视觉推理", "vision.input", "vision.output", ["filesystem"], "medium", "before_external_effect"],
  ["project-packaging", "项目打包", "package.input", "package.output", ["filesystem"], "low", "before_external_effect"],
].map(([id, name, inputSchemaKey, outputSchemaKey, requiredTools, riskLevel, confirmationPolicy]) => ({
  id: id as string,
  ownerExpert: "smart_engineer",
  name: name as string,
  inputSchemaKey: inputSchemaKey as string,
  outputSchemaKey: outputSchemaKey as string,
  requiredTools: requiredTools as string[],
  riskLevel: riskLevel as SkillDefinition["riskLevel"],
  confirmationPolicy: confirmationPolicy as SkillDefinition["confirmationPolicy"],
}));
