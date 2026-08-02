# 系统架构

## 模块

### UI
- ProjectCreate
- ProjectOverview
- ExpertConversation
- ExpertSidebar
- WorkPanel
- ArtifactPanel
- DevicePanel

### Application
- ProjectApplicationService
- RouterApplicationService
- ExpertApplicationService
- CoordinatorApplicationService
- ArtifactApplicationService
- DeviceApplicationService

### Runtime
- AgentRuntime
- SkillRuntime
- ContextAssembler
- EntryRouter
- ProjectCoordinator
- ModelRouter
- ToolRunner

### Domain
- Project
- ExpertWorkspace
- ConversationThread
- SharedFact
- ProjectDecision
- Artifact
- ArtifactDependency
- Task
- PendingItem
- Handoff
- Device
- SkillRun
- ToolRun

### Infrastructure
- ProjectRepository
- ConversationRepository
- ArtifactRepository
- CoordinationRepository
- DeviceRepository
- FileStorage
- KnowledgeRetriever
- LlmProvider
- LocalToolAdapter

## 依赖方向

UI → Application → Domain Ports
Runtime → Domain Ports
Infrastructure → Domain Ports 的实现

Domain 不依赖 UI、数据库、模型厂商和工具实现。
