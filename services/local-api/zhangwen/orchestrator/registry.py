"""Built-in Agent Registry for ZW-007."""

from __future__ import annotations

from zhangwen.orchestrator.models import AgentCapability, AgentDefinition


BUILT_IN_AGENTS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        id="orchestrator",
        name="Orchestrator",
        description="编排项目执行计划、确认节点和恢复流程。",
        capabilities=[AgentCapability.ORCHESTRATE, AgentCapability.REVIEW],
    ),
    AgentDefinition(
        id="spec-agent",
        name="Spec Agent",
        description="后续阶段生成工程规格、BOM 和 IO Map。",
        capabilities=[AgentCapability.SPEC],
    ),
    AgentDefinition(
        id="code-agent",
        name="Code Agent",
        description="后续阶段生成和验证 MicroPython 工程代码。",
        capabilities=[AgentCapability.CODE],
    ),
    AgentDefinition(
        id="cad-agent",
        name="CAD Agent",
        description="后续阶段生成结构件和 3D 产物。",
        capabilities=[AgentCapability.CAD],
    ),
    AgentDefinition(
        id="deploy-agent",
        name="Deploy Agent",
        description="后续阶段管理设备连接、上传和部署验证。",
        capabilities=[AgentCapability.DEPLOY],
    ),
    AgentDefinition(
        id="publish-agent",
        name="Publish Agent",
        description="后续阶段打包项目并准备分享材料。",
        capabilities=[AgentCapability.PUBLISH],
    ),
    AgentDefinition(
        id="lesson-agent",
        name="Lesson Agent",
        description="后续阶段生成教师版和学生版教案。",
        capabilities=[AgentCapability.LESSON],
    ),
)


class AgentRegistry:
    def list_agents(self) -> list[AgentDefinition]:
        return list(BUILT_IN_AGENTS)

    def get_agent(self, agent_id: str) -> AgentDefinition:
        for agent in BUILT_IN_AGENTS:
            if agent.id == agent_id:
                return agent
        raise ValueError("Agent 不存在。")
