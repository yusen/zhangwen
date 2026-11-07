"""Portable checkpoints of the existing Project/Conversation/Artifact records.

Folder I/O is browser-only. Import creates an isolated project in one original
ProjectRepository transaction; existing projects are never overwritten.
"""
from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime
from typing import Literal
from fastapi import HTTPException
from pydantic import Field, field_validator, model_validator
from zhangwen.artifacts.models import ArtifactPreview, ArtifactPreviewKind, ArtifactPreviewSection
from zhangwen.llm.contracts import ChatMessage, ChatMessageStatus, ChatRole
from .models import Boundary, CodeInput, CreateInput
from .structure import StructureCheckpoint, export_structure, prepare_structure_import, insert_structure_import
from .legacy_names import workspace_message
from .references import ReferenceVersion, Citation, list_references, insert_reference
from .chat_coding import Checkpoint as ChatCodingCheckpoint, load_checkpoint, insert_checkpoint, insert_conversation_records
from .programming_modes import board_mode, task_file
from . import lua_coding, workflow
from .workflow_models import Checkpoint as WorkflowCheckpoint
from .workflow_portable import checkpoint as portable_workflow
SNAPSHOT_MAX_BYTES = 32 * 1024 * 1024

def sha(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()

class SnapshotProject(Boundary):
    programmingMode: Literal['chat-coding'] | None = None
    name: str = Field(min_length=1, max_length=80)
    boardId: str = Field(max_length=150)
    componentIds: list[str] = Field(max_length=32)
    revision: int = Field(ge=1, strict=True)

    @field_validator('name')
    @classmethod
    def name_text(cls, value):
        return CreateInput.name_not_blank(value)

class SnapshotVersion(Boundary):
    programmingMode: Literal['chat-coding'] | None = None
    revision: int = Field(ge=1, strict=True)
    code: str = Field(max_length=65536)
    checksum: str = Field(pattern='^[a-f0-9]{64}$')
    createdAt: str = Field(min_length=1, max_length=60)
    source: Literal['saved', 'ai'] = 'saved'
    boardId: str | None = Field(default=None, min_length=1, max_length=150)
    messageId: str | None = Field(default=None, min_length=1, max_length=150)
    name: str | None = Field(default=None, max_length=80)

    @model_validator(mode='after')
    def integrity(self):
        CodeInput.code_size(self.code)
        if sha(self.code) != self.checksum:
            raise ValueError('历史代码摘要不一致。')
        datetime.fromisoformat(self.createdAt)
        return self

class SnapshotMessage(Boundary):
    id: str = Field(min_length=1, max_length=150)
    role: Literal['user', 'assistant']
    componentIds: list[str] | None = Field(default=None, max_length=32)
    intent: Literal['integration', 'lua-coding', 'idea-coding'] | None = None
    integrationModuleId: str | None = Field(default=None, min_length=1, max_length=150)
    content: str = Field(max_length=80000)
    status: Literal['COMPLETED', 'FAILED', 'CANCELED']
    boardId: str | None = Field(default=None, min_length=1, max_length=150)
    createdAt: str = Field(min_length=1, max_length=60)
    references: list[Citation] | None = Field(default=None, max_length=120)
    referenceNotice: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def integration_target(self):
        if self.integrationModuleId is not None and (self.intent != 'integration' or self.integrationModuleId not in (self.componentIds or [])):
            raise ValueError('历史联调对象与该条消息的模块选择不一致。')
        return self

    @field_validator('createdAt')
    @classmethod
    def timestamp(cls, value):
        datetime.fromisoformat(value)
        return value

class ProjectSnapshot(Boundary):
    workflow: WorkflowCheckpoint | None = None
    luaCoding: lua_coding.Checkpoint | None = None
    chatCoding: ChatCodingCheckpoint | None = None
    format: Literal['zhangwen-project']
    schemaVersion: Literal[1]
    portableId: str = Field(pattern='^[A-Za-z0-9_-]{1,150}$')
    project: SnapshotProject
    versions: list[SnapshotVersion] = Field(min_length=1, max_length=1000)
    messages: list[SnapshotMessage] = Field(max_length=10000)
    structure: StructureCheckpoint | None = None
    references: list[ReferenceVersion] | None = Field(default=None, max_length=200)

    @model_validator(mode='after')
    def pointers(self):
        keys = [(r.id, r.version) for r in self.references or []]
        if len(set(keys)) != len(keys) or len({r.id for r in self.references or []}) > 20:
            raise ValueError('资料历史版本重复。')
        for reference_id in {r.id for r in self.references or []}:
            numbers = sorted((r.version for r in self.references if r.id == reference_id))
            if numbers != list(range(1, len(numbers) + 1)):
                raise ValueError('资料版本须从1开始连续。')
        numbers = [version.revision for version in self.versions]
        if len(set(numbers)) != len(numbers) or min(numbers) != 1 or max(numbers) != len(numbers):
            raise ValueError('代码历史版本须从1开始连续且不重复。')
        current = next((v for v in self.versions if v.revision == self.project.revision), None)
        if current is None or current.source != 'saved':
            raise ValueError('当前程序必须指向已保存版本，不能直接采用AI候选。')
        ids = [item.id for item in self.messages]
        if len(set(ids)) != len(ids):
            raise ValueError('对话记录标识重复。')
        messages = {item.id: item for item in self.messages}
        source_map = {(r.id, r.version): r for r in self.references or []}
        for message in self.messages:
            for citation in message.references or []:
                source = source_map.get((citation.id, citation.version))
                if source is None or source.name != citation.name or citation.startLine > citation.endLine or (citation.endLine > len(source.text.splitlines())) or (citation.text not in '\n'.join(source.text.splitlines()[citation.startLine - 1:citation.endLine])):
                    raise ValueError('对话引用与资料版本不一致。')
        for version in self.versions:
            if version.messageId is None:
                continue
            message = messages.get(version.messageId)
            if version.source != 'ai' or message is None or message.role != 'assistant' or (message.status != 'COMPLETED') or (version.boardId != message.boardId):
                raise ValueError('AI代码版本须关联同主控的完整助手回复。')
        workflow.validate_snapshot(self.workflow, self)
        return self

def normalized(value: dict) -> dict:
    return ProjectSnapshot.model_validate(value).model_dump(exclude_none=True)

def export_project(repo, project_id: str) -> dict:
    project = repo.get(project_id)
    with repo.connect() as conn:
        native = conn.execute('SELECT v.preview_json FROM artifacts a JOIN artifact_versions v ON v.id=a.current_version_id WHERE a.id=? AND a.project_id=?', ('zhangwen_idea_' + project_id, project_id)).fetchone()
    native_data = json.loads(json.loads(native[0])['code']) if native else {}
    if native_data.get('versions') or native_data.get('jobs'):
        raise HTTPException(409, '本项目含尚未发布的Idea开发内容，请在完整开发版导出；原数据已保留。')
    with repo.connect() as conn:
        portable_id = conn.execute('SELECT COALESCE(portable_id, project_id) FROM zhangwen_workspaces WHERE project_id=?', (project_id,)).fetchone()[0]
        portable_messages = {row['id']: json.loads(row['metadata_json'] or '{}').get('portableMessageId', row['id']) for row in conn.execute(f'SELECT id, metadata_json FROM messages WHERE project_id=? AND {workspace_message()}', (project_id,))}
    if any((item['status'] not in {'COMPLETED', 'FAILED', 'CANCELED'} for item in project['messages'])):
        raise HTTPException(409, '对话仍在生成，完成或取消后再保存项目文件夹。')
    versions = repo.versions(project_id)
    if len(versions) > 1000 or len(project['messages']) > 10000:
        raise HTTPException(413, '项目超过1000个代码版本或10000条对话的文件夹容量，未截断或覆盖。请保留本机数据并另行备份。')
    result = normalized({'format': 'zhangwen-project', 'schemaVersion': 1, 'portableId': portable_id, 'project': {key: project[key] for key in ('name', 'boardId', 'componentIds', 'revision', 'programmingMode') if key in project}, 'versions': [{**item, **({'messageId': portable_messages.get(item['messageId'], item['messageId'])} if item.get('messageId') else {})} for item in versions], 'messages': [{**item, 'id': portable_messages[item['id']]} for item in project['messages']], **({'structure': structure} if (structure := export_structure(repo, project_id)) else {}), **({'references': refs} if (refs := list_references(repo, project_id, history=True)) else {}), **({'chatCoding': checkpoint.model_dump(exclude_none=True)} if (checkpoint := load_checkpoint(repo, project_id)[1]).records else {}), **({'luaCoding': lua.model_dump(exclude_none=True)} if (lua := lua_coding.load(repo, project_id)).versions or lua.wifiSetups else {}), **({'workflow': portable_workflow(learning.model_dump(), structure)} if (learning := workflow.load(repo, project_id)).revision else {})})
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > SNAPSHOT_MAX_BYTES:
        raise HTTPException(413, '项目快照超过32MiB，未截断或覆盖文件夹。请保留本机数据并另行备份。')
    return result

def import_project(repo, snapshot: ProjectSnapshot) -> dict:
    value = snapshot.model_dump(exclude_none=True)
    if len(json.dumps(value, ensure_ascii=False).encode('utf-8')) > SNAPSHOT_MAX_BYTES:
        raise HTTPException(413, '项目快照超过32MiB。')
    hardware = repo.hardware_revisions(snapshot.project.boardId, snapshot.project.componentIds)
    if snapshot.luaCoding and board_mode(repo, snapshot.project.boardId) != 'chat-coding':
        raise HTTPException(422, 'Lua历史只能导入Mosaico项目。')
    if (snapshot.project.programmingMode or 'micropython') != board_mode(repo, snapshot.project.boardId):
        raise HTTPException(422, '项目编程方式与主控资料不一致。')
    for item in snapshot.versions:
        if (item.programmingMode or 'micropython') != board_mode(repo, item.boardId or ''):
            raise HTTPException(422, '历史任务编程方式与主控资料不一致。')
    prepare_structure_import(repo, snapshot.structure)
    with repo.connect() as conn:
        matches = conn.execute('SELECT project_id FROM zhangwen_workspaces WHERE COALESCE(portable_id, project_id)=?', (snapshot.portableId,)).fetchall()
    for row in matches:
        try:
            if export_project(repo, row[0]) == value:
                return repo.get(row[0])
        except HTTPException:
            continue

    def after_create(conn, project_id, now):
        artifact_id = f'zhangwen_code_{project_id}'
        message_ids = {item.id: 'msg_' + uuid.uuid4().hex for item in snapshot.messages}
        version_ids = {item.revision: f'artifact_version_{artifact_id}_{uuid.uuid4().hex}' for item in snapshot.versions}
        conn.execute("INSERT INTO artifacts (id, project_id, title, kind, status, source_agent_id,\n            current_version_id, created_at, updated_at) VALUES (?, ?, ?, 'CODE', 'DRAFT', 'zhangwen-import', ?, ?, ?)", (artifact_id, project_id, task_file(repo, snapshot.project.boardId), version_ids[max(version_ids)], now, now))
        for item in snapshot.versions:
            preview = ArtifactPreview(kind=ArtifactPreviewKind.CODE, code=item.code, language='text' if item.programmingMode == 'chat-coding' else 'python', summary='从用户选择的项目文件夹恢复，未上传或运行。')
            if item.name is not None:
                preview.sections = [ArtifactPreviewSection(id='zhangwen-version-name', title='版本名称', content=item.name)]
            conn.execute("INSERT INTO artifact_versions (id, artifact_id, project_id, version, status,\n                mime_type, preview_json, dependencies_json, source_entity_type, source_entity_id, checksum, created_at)\n                VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?)", (version_ids[item.revision], artifact_id, project_id, item.revision, 'NEEDS_REVIEW' if item.source == 'ai' else 'DRAFT', 'text/plain' if item.programmingMode == 'chat-coding' else 'text/x-python', preview.model_dump_json(), 'zhangwen_ai_code' if item.source == 'ai' else 'zhangwen_code', message_ids.get(item.messageId, item.messageId or uuid.uuid4().hex), item.checksum, item.createdAt))
            if item.boardId:
                conn.execute('INSERT INTO zhangwen_code_metadata(version_id, board_id) VALUES (?, ?)', (version_ids[item.revision], item.boardId))
        conn.execute('INSERT INTO zhangwen_workspaces (project_id, board_id, component_ids, hardware_revisions,\n            artifact_version_id, revision, updated_at, portable_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (project_id, snapshot.project.boardId, json.dumps(snapshot.project.componentIds), json.dumps(hardware), version_ids[snapshot.project.revision], snapshot.project.revision, now, snapshot.portableId))
        conversation_id = conn.execute('SELECT id FROM conversations WHERE project_id=? ORDER BY created_at LIMIT 1', (project_id,)).fetchone()[0]
        for item in snapshot.messages:
            metadata = {'zhangwen': True, 'portableMessageId': item.id}
            if item.boardId:
                metadata['boardId'] = item.boardId
            if item.componentIds is not None:
                metadata['componentIds'] = item.componentIds
            if item.intent:
                metadata['intent'] = item.intent
            if item.integrationModuleId is not None:
                metadata['integrationModuleId'] = item.integrationModuleId
            if item.references is not None:
                metadata['references'] = [r.model_dump() for r in item.references]
            if item.referenceNotice is not None:
                metadata['referenceNotice'] = item.referenceNotice
            message = ChatMessage(id=message_ids[item.id], role=ChatRole(item.role), content=item.content, status=ChatMessageStatus(item.status), createdAt=item.createdAt, updatedAt=item.createdAt, metadata=metadata)
            repo.projects._insert_message(conn, conversation_id, project_id, message)
        insert_structure_import(repo, conn, project_id, snapshot.structure)
        if snapshot.workflow:
            workflow.insert(repo, conn, project_id, snapshot.workflow, snapshot.workflow.messages)
        if snapshot.luaCoding:
            lua_coding.insert(repo, conn, project_id, snapshot.luaCoding)
        if snapshot.chatCoding:
            insert_checkpoint(repo, conn, project_id, snapshot.chatCoding)
            insert_conversation_records(repo, conn, project_id, snapshot.chatCoding.records)
        for item in sorted(snapshot.references or [], key=lambda r: (r.id, r.version)):
            insert_reference(conn, project_id, item.model_dump(exclude_none=True), now)
    workspace = repo.projects.create_project_from_idea(idea='从本地项目文件夹恢复' + ('Chat Coding项目' if snapshot.project.programmingMode == 'chat-coding' else 'MicroPython项目'), project_name=snapshot.project.name, initial_expert=None, participating_experts=[], after_create=after_create)
    return repo.get(workspace.project.id)
