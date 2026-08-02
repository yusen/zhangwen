import type { ExpertType } from "../domain/types";

export interface ExpertDefinition {
  id: ExpertType;
  displayName: string;
  description: string;
  promptKey: string;
  visible: true;
  artifactTypes: string[];
  skillIds: string[];
}

export const EXPERTS: Record<ExpertType, ExpertDefinition> = {
  problem_guide: {
    id: "problem_guide",
    displayName: "问题引导师",
    description: "从困惑到方案，完成立项、实验与教学设计。",
    promptKey: "problem-guide",
    visible: true,
    artifactTypes: [
      "project_brief",
      "project_proposal",
      "experiment_plan",
      "teaching_design",
      "lesson_plan",
      "learning_task",
      "assessment_rubric",
    ],
    skillIds: [
      "idea-guidance",
      "problem-definition",
      "project-proposal",
      "experiment-design",
      "pbl-course-design",
      "assessment-rubric",
    ],
  },
  smart_engineer: {
    id: "smart_engineer",
    displayName: "智能工程师",
    description: "完成硬件、代码、IoT、数据与 AI 部署。",
    promptKey: "smart-engineer",
    visible: true,
    artifactTypes: [
      "hardware_plan",
      "bom",
      "io_map",
      "wiring_table",
      "electrical_check",
      "source_code",
      "iot_contract",
      "data_analysis",
      "ai_deployment",
      "mock_test_report",
      "project_package",
    ],
    skillIds: [
      "hardware-selection",
      "bom-generation",
      "io-map",
      "wiring",
      "electrical-check",
      "micropython-generation",
      "arduino-generation",
      "code-review",
      "mock-test",
      "iot-mqtt",
      "iot-http",
      "data-acquisition",
      "data-analysis",
      "ai-deployment",
      "vision-inference",
      "project-packaging",
    ],
  },
  structure_engineer: {
    id: "structure_engineer",
    displayName: "结构工程师",
    description: "完成外观、结构、装配、建模与打印适配。",
    promptKey: "structure-engineer",
    visible: true,
    artifactTypes: [
      "appearance_concept",
      "structure_spec",
      "dimension_sheet",
      "assembly_plan",
      "stl_model",
      "step_model",
      "three_mf_model",
      "print_profile",
      "printability_report",
    ],
    skillIds: [
      "appearance-concept",
      "enclosure-design",
      "mount-design",
      "assembly-check",
      "tolerance-check",
      "printability-check",
      "stl-export",
      "step-export",
      "print-profile",
    ],
  },
};
