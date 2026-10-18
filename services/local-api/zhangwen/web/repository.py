"""掌问 metadata and immutable code use the existing Project/Artifact database.

No old classroom work is automatically enrolled. Only explicitly created
zhangwen_workspaces are editable through this adapter.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import HTTPException

from zhangwen.artifacts.models import ArtifactKind, ArtifactStatus
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.hardware.hardware_skills import HardwareSkillRepository, HardwareSkillNotFoundError, HardwareSkillValidationError
from zhangwen.hardware.models import HardwareCategory
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.projects.repository import ProjectRepository
from zhangwen.web.models import CodeInput, CreateInput, DEFAULT_CODE, SaveInput
from zhangwen.web.hardware import WebHardwareRepository
from zhangwen.web.replies import reply_code
from zhangwen.web.version_names import code_name
from .legacy_names import migrate_tables, workspace_message, artifact_id, AI_SOURCES
from .programming import programming_diagnostics


def checksum(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class WebRepository:
    def __init__(self, data_dir: Path) -> None:
        self.projects = ProjectRepository(data_dir)
        self.db = self.projects.db_path
        self.artifacts = ArtifactRepository(self.db)
        self.skills = WebHardwareRepository(data_dir, self.db)
        self.lock = RLock()
        migrate_tables(self.connect())
        seed_default_components(self.db)
        self.skills.install_release_catalog()
        self.skills.install_bundled_catalog()
        self.skills.migrate_legacy_rows()
        self.skills.install_web_boards()
        self.skills.install_vendor_catalog()
        self.skills.install_module_guides()
        self.skills.refresh_active_catalog()
        with self.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS zhangwen_workspaces (
                project_id TEXT PRIMARY KEY REFERENCES projects(id),
                board_id TEXT NOT NULL, component_ids TEXT NOT NULL,
                hardware_revisions TEXT NOT NULL, artifact_version_id TEXT,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )''')
            if 'portable_id' not in {row[1] for row in conn.execute('PRAGMA table_info(zhangwen_workspaces)')}:
                conn.execute('ALTER TABLE zhangwen_workspaces ADD COLUMN portable_id TEXT')
            conn.execute('''CREATE TABLE IF NOT EXISTS zhangwen_code_metadata (
                version_id TEXT PRIMARY KEY REFERENCES artifact_versions(id), board_id TEXT
            )''')
        # An interrupted provider request must never remain "generating" forever.
        self.projects.normalize_stale_streaming()
        self.recover_ai_candidates()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def artifact_id(self, project_id: str, kind: str = 'code') -> str:
        with self.connect() as conn:
            return artifact_id(conn, project_id, kind)

    def hardware_revisions(self, board: str, components: list[str]) -> dict[str, str]:
        if len(set(components)) != len(components) or board in components:
            raise HTTPException(422, "器件重复或将主控板加入了外设清单。")
        revisions: dict[str, str] = {}
        for component in ([board] if board else []) + components:
            try:
                skill = self.skills.get_active_by_component_id(component)
            except (ValueError, KeyError, HardwareSkillNotFoundError, HardwareSkillValidationError) as exc:
                raise HTTPException(422, "所选硬件不存在或未激活，请刷新硬件库。") from exc
            if (bool(board) and component == board) != (skill.category == HardwareCategory.MCU):
                raise HTTPException(422, "须选择一个主控板；外设清单不能包含其他主控板。")
            revisions[component] = skill.revision
        return revisions

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute('''SELECT m.*, p.name FROM zhangwen_workspaces m
                JOIN projects p ON p.id=m.project_id ORDER BY m.updated_at DESC''').fetchall()
        return [self.summary(row) for row in rows]

    @staticmethod
    def summary(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["project_id"], "name": row["name"], "boardId": row["board_id"],
                "componentIds": json.loads(row["component_ids"]), "revision": row["revision"],
                "updatedAt": row["updated_at"]}

    def get(self, project_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute('''SELECT m.*, p.name, v.preview_json, v.checksum
                FROM zhangwen_workspaces m JOIN projects p ON p.id=m.project_id
                LEFT JOIN artifact_versions v ON v.id=m.artifact_version_id
                WHERE m.project_id=?''', (project_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "此项目不属于独立 掌问 工作区。历史课程项目未被转换。")
            messages = conn.execute(f'''SELECT id, role, content, status, created_at AS createdAt,
                COALESCE(json_extract(metadata_json, '$.boardId'), ?) AS boardId,
                json_extract(metadata_json, '$.componentIds') AS componentIds,
                json_extract(metadata_json, '$.intent') AS intent FROM messages
                WHERE project_id=? AND {workspace_message()}
                ORDER BY rowid''', (row['board_id'], project_id)).fetchall()
        return {**self.summary(row), "code": json.loads(row["preview_json"])["code"] if row["preview_json"] else DEFAULT_CODE,
                "checksum": row["checksum"] or checksum(DEFAULT_CODE),
                "messages": [{key: json.loads(value) if key == 'componentIds' else value
                              for key, value in dict(item).items() if value is not None} for item in messages]}

    def create(self, request: CreateInput) -> dict[str, Any]:
        revisions = self.hardware_revisions(request.boardId, request.componentIds)
        now = datetime.now(UTC).isoformat()

        def after_create(conn: sqlite3.Connection, project_id: str, _: str) -> None:
            conn.execute('''INSERT INTO zhangwen_workspaces
                (project_id, board_id, component_ids, hardware_revisions, updated_at)
                VALUES (?, ?, ?, ?, ?)''', (project_id, request.boardId, json.dumps(request.componentIds), json.dumps(revisions), now))

        with self.lock:
            workspace = self.projects.create_project_from_idea(
                idea="独立 MicroPython 编程", project_name=request.name,
                initial_expert=None, participating_experts=[], after_create=after_create,
            )
            project_id = workspace.project.id
            return self._save(project_id, SaveInput(
                name=request.name, boardId=request.boardId, code=request.code, componentIds=request.componentIds, expectedRevision=1,
            ), initial=True)

    def save(self, project_id: str, request: SaveInput) -> dict[str, Any]:
        with self.lock:
            return self._save(project_id, request)

    def _save(self, project_id: str, request: SaveInput, *, initial: bool = False) -> dict[str, Any]:
        current = self.get(project_id)
        if not initial and request.expectedRevision != current["revision"]:
            raise HTTPException(409, "项目已被另一个页面修改。请先导出当前代码，再重新打开项目。")
        revisions = self.hardware_revisions(request.boardId, request.componentIds)
        artifact_id = self.artifact_id(project_id)
        with self.connect() as conn:
            version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?", (artifact_id,)).fetchone()[0]
        # Persist immutable candidate first. A crash can leave an unreferenced
        # candidate, but cannot point the workspace at a partially saved version.
        saved = self.artifacts.upsert_text_artifact(
            artifact_id=artifact_id, project_id=project_id, title="main.py", kind=ArtifactKind.CODE,
            status=ArtifactStatus.DRAFT, source_agent_id="zhangwen-manual", source_entity_type="zhangwen_code",
            source_entity_id=uuid.uuid4().hex, source_version=version, content=request.code,
            summary="手工确认的 MicroPython 文件；尚未证明实物运行。",
            mime_type="text/x-python", language="python",
        )
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute('INSERT INTO zhangwen_code_metadata(version_id, board_id) VALUES (?, ?)', (saved.id, request.boardId))
            conn.execute(f"""UPDATE messages SET metadata_json=json_set(metadata_json, '$.boardId', ?)
                WHERE project_id=? AND {workspace_message()}
                AND json_extract(metadata_json, '$.boardId') IS NULL""", (current['boardId'], project_id))
            conn.execute('''UPDATE zhangwen_workspaces SET board_id=?, component_ids=?,
                hardware_revisions=?, artifact_version_id=?, revision=?, updated_at=? WHERE project_id=?''',
                (request.boardId, json.dumps(request.componentIds), json.dumps(revisions), saved.id, version, now, project_id))
            conn.execute("UPDATE projects SET name=?, updated_at=? WHERE id=?", (request.name.strip(), now, project_id))
        return self.get(project_id)

    def versions(self, project_id: str) -> list[dict[str, Any]]:
        self.get(project_id)
        with self.connect() as conn:
            rows = conn.execute('''SELECT v.version, v.preview_json, v.checksum, v.created_at,
                v.source_entity_type, s.id AS message_id, s.content AS reply, m.board_id FROM artifact_versions v
                LEFT JOIN zhangwen_code_metadata m ON m.version_id=v.id
                LEFT JOIN messages s ON s.id=v.source_entity_id AND s.project_id=v.project_id
                WHERE v.artifact_id=? ORDER BY v.version DESC''', (self.artifact_id(project_id),)).fetchall()
        return [{"revision": row["version"], "code": json.loads(row["preview_json"])["code"],
                 "checksum": row["checksum"], "createdAt": row["created_at"],
                 "source": "ai" if row["source_entity_type"] in AI_SOURCES else "saved",
                 "name": code_name(json.loads(row['preview_json'])['code'], row['reply']),
                 **({"messageId": row['message_id']} if row['source_entity_type'] in AI_SOURCES and row['message_id'] else {}),
                 **({"boardId": row["board_id"]} if row["board_id"] else {})} for row in rows]

    def record_ai_code(self, project_id: str, board_id: str, message_id: str, reply: str) -> None:
        code = reply_code(reply)
        if code is None:
            return
        if len(code.encode('utf-8')) > 65_536 or '\x00' in code:
            return
        with self.lock:
            self.get(project_id)
            artifact_id = self.artifact_id(project_id)
            with self.connect() as conn:
                if conn.execute('SELECT 1 FROM artifact_versions WHERE artifact_id=? AND source_entity_id=?', (artifact_id, message_id)).fetchone():
                    return
                revision = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?', (artifact_id,)).fetchone()[0]
            saved = self.artifacts.upsert_text_artifact(
                artifact_id=artifact_id, project_id=project_id, title='main.py', kind=ArtifactKind.CODE,
                status=ArtifactStatus.NEEDS_REVIEW, source_agent_id='zhangwen-ai', source_entity_type='zhangwen_ai_code',
                source_entity_id=message_id, source_version=revision, content=code,
                summary='AI生成的待接受代码，未保存为当前程序、未上传或运行。', mime_type='text/x-python', language='python',
            )
            with self.connect() as conn:
                conn.execute('INSERT INTO zhangwen_code_metadata(version_id, board_id) VALUES (?, ?)', (saved.id, board_id))
            # Workspace revision/pointer stays at the last explicitly saved code.

    def recover_ai_candidates(self) -> None:
        # Idempotent startup repair for completed 掌问 replies previously rejected
        # solely for presentation. Original messages and saved pointers stay intact.
        with self.connect() as conn:
            rows = conn.execute(f'''SELECT s.id, s.project_id, s.content,
                json_extract(s.metadata_json, '$.boardId') AS board_id FROM messages s
                JOIN zhangwen_workspaces w ON w.project_id=s.project_id
                LEFT JOIN artifact_versions v ON v.project_id=s.project_id
                    AND v.source_entity_id=s.id AND v.source_entity_type IN (?, ?)
                WHERE s.role='assistant' AND s.status='COMPLETED'
                    AND {workspace_message('s.metadata_json')}
                    AND json_type(s.metadata_json, '$.boardId')='text'
                    AND v.id IS NULL ORDER BY s.rowid''', AI_SOURCES).fetchall()
        for row in rows:
            if row['board_id']:
                code = reply_code(row['content'])
                if code is None:
                    continue
                try:
                    ast.parse(code)
                except SyntaxError:
                    continue
                self.record_ai_code(row['project_id'], row['board_id'], row['id'], row['content'])

    def export_project(self, project_id: str) -> dict[str, Any]:
        from .portable import export_project
        with self.lock:
            return export_project(self, project_id)

    def import_project(self, snapshot) -> dict[str, Any]:
        from .portable import import_project
        with self.lock:
            return import_project(self, snapshot)

    def check(self, request: CodeInput) -> dict[str, Any]:
        self.hardware_revisions(request.boardId, request.componentIds)
        diagnostics: list[dict[str, Any]] = []
        try:
            compile(request.code, "main.py", "exec")
            diagnostics.append({"severity": "PASS", "message": "Python 语法检查通过（未执行代码）。"})
        except (SyntaxError, ValueError, RecursionError) as exc:
            diagnostics.append({"severity": "FAIL", "message": str(exc), "line": getattr(exc, "lineno", None)})
        rules = self.skills.validate_component_ids([request.boardId, *request.componentIds])
        diagnostics.extend({"severity": item.severity.value, "message": item.message + " " + item.details} for item in rules.checks)
        diagnostics.extend(programming_diagnostics(request.code, request.boardId))
        diagnostics.append({"severity": "WARNING", "message": "静态检查仅覆盖语法与部分已知 API 错误，不能验证设备固件、实际接线、引脚占用或实物行为。"})
        return {"valid": not any(item["severity"] == "FAIL" for item in diagnostics), "checksum": checksum(request.code), "diagnostics": diagnostics}

    def manifest(self, project_id: str, revision: int) -> dict[str, Any]:
        with self.lock:
            project = self.get(project_id)
            if not project['boardId']:
                raise HTTPException(422, '请先在主界面选择主控板，再上传程序。')
            if project["revision"] != revision:
                raise HTTPException(409, "上传版本已变更，请重新保存并核对清单。")
            request = CodeInput(**{key: project[key] for key in ("code", "boardId", "componentIds")})
            checked = self.check(request)
            if not checked['valid']:
                raise HTTPException(422, {'message':'上传被检查拦住，请先修复下方错误。', 'check':checked})
            revisions = self.hardware_revisions(project["boardId"], project["componentIds"])
            with self.connect() as conn:
                frozen = json.loads(conn.execute("SELECT hardware_revisions FROM zhangwen_workspaces WHERE project_id=?", (project_id,)).fetchone()[0])
            if frozen != revisions:
                raise HTTPException(409, "硬件资料已更新，请核对后保存新版本。")
            return {"projectId": project_id, "revision": revision, "boardId": project["boardId"],
                    "hardwareRevisions": revisions, "files": [{"path": "main.py", "content": project["code"],
                    "sha256": project["checksum"], "size": len(project["code"].encode("utf-8"))}]}
