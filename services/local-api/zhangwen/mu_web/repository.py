"""Mu metadata and immutable code use the existing Project/Artifact database.

No old classroom work is automatically enrolled. Only explicitly created
mu_workspaces are editable through this adapter.
"""
from __future__ import annotations

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
from zhangwen.mu_web.models import CodeInput, CreateInput, DEFAULT_CODE, SaveInput
from zhangwen.mu_web.hardware import WebHardwareRepository
from zhangwen.mu_web.replies import reply_code


def checksum(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class MuRepository:
    def __init__(self, data_dir: Path) -> None:
        self.projects = ProjectRepository(data_dir)
        self.db = self.projects.db_path
        self.artifacts = ArtifactRepository(self.db)
        self.skills = WebHardwareRepository(data_dir, self.db)
        self.lock = RLock()
        seed_default_components(self.db)
        self.skills.install_release_catalog()
        self.skills.install_bundled_catalog()
        self.skills.migrate_legacy_rows()
        self.skills.install_web_boards()
        self.skills.install_vendor_catalog()
        self.skills.refresh_active_catalog()
        with self.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS mu_workspaces (
                project_id TEXT PRIMARY KEY REFERENCES projects(id),
                board_id TEXT NOT NULL, component_ids TEXT NOT NULL,
                hardware_revisions TEXT NOT NULL, artifact_version_id TEXT,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )''')
            if 'portable_id' not in {row[1] for row in conn.execute('PRAGMA table_info(mu_workspaces)')}:
                conn.execute('ALTER TABLE mu_workspaces ADD COLUMN portable_id TEXT')
            conn.execute('''CREATE TABLE IF NOT EXISTS mu_code_metadata (
                version_id TEXT PRIMARY KEY REFERENCES artifact_versions(id), board_id TEXT
            )''')
        # An interrupted provider request must never remain "generating" forever.
        self.projects.normalize_stale_streaming()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def hardware_revisions(self, board: str, components: list[str]) -> dict[str, str]:
        if len(set(components)) != len(components) or board in components:
            raise HTTPException(422, "器件重复或将主控板加入了外设清单。")
        revisions: dict[str, str] = {}
        for index, component in enumerate([board, *components]):
            try:
                skill = self.skills.get_active_by_component_id(component)
            except (ValueError, KeyError, HardwareSkillNotFoundError, HardwareSkillValidationError) as exc:
                raise HTTPException(422, "所选硬件不存在或未激活，请刷新硬件库。") from exc
            if (index == 0) != (skill.category == HardwareCategory.MCU):
                raise HTTPException(422, "须选择一个主控板；外设清单不能包含其他主控板。")
            revisions[component] = skill.revision
        return revisions

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute('''SELECT m.*, p.name FROM mu_workspaces m
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
                FROM mu_workspaces m JOIN projects p ON p.id=m.project_id
                LEFT JOIN artifact_versions v ON v.id=m.artifact_version_id
                WHERE m.project_id=?''', (project_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "此项目不属于独立 Mu 工作区。历史课程项目未被转换。")
            messages = conn.execute('''SELECT id, role, content, status, created_at AS createdAt,
                COALESCE(json_extract(metadata_json, '$.boardId'), ?) AS boardId FROM messages
                WHERE project_id=? AND json_extract(metadata_json, '$.mu')=1
                ORDER BY rowid''', (row['board_id'], project_id)).fetchall()
        return {**self.summary(row), "code": json.loads(row["preview_json"])["code"] if row["preview_json"] else DEFAULT_CODE,
                "checksum": row["checksum"] or checksum(DEFAULT_CODE),
                "messages": [{key: value for key, value in dict(item).items() if value is not None} for item in messages]}

    def create(self, request: CreateInput) -> dict[str, Any]:
        revisions = self.hardware_revisions(request.boardId, request.componentIds)
        now = datetime.now(UTC).isoformat()

        def after_create(conn: sqlite3.Connection, project_id: str, _: str) -> None:
            conn.execute('''INSERT INTO mu_workspaces
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
        artifact_id = f"mu_code_{project_id}"
        with self.connect() as conn:
            version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?", (artifact_id,)).fetchone()[0]
        # Persist immutable candidate first. A crash can leave an unreferenced
        # candidate, but cannot point the workspace at a partially saved version.
        saved = self.artifacts.upsert_text_artifact(
            artifact_id=artifact_id, project_id=project_id, title="main.py", kind=ArtifactKind.CODE,
            status=ArtifactStatus.DRAFT, source_agent_id="mu-manual", source_entity_type="mu_code",
            source_entity_id=uuid.uuid4().hex, source_version=version, content=request.code,
            summary="手工确认的 MicroPython 文件；尚未证明实物运行。",
            mime_type="text/x-python", language="python",
        )
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute('INSERT INTO mu_code_metadata(version_id, board_id) VALUES (?, ?)', (saved.id, request.boardId))
            conn.execute("""UPDATE messages SET metadata_json=json_set(metadata_json, '$.boardId', ?)
                WHERE project_id=? AND json_extract(metadata_json, '$.mu')=1
                AND json_extract(metadata_json, '$.boardId') IS NULL""", (current['boardId'], project_id))
            conn.execute('''UPDATE mu_workspaces SET board_id=?, component_ids=?,
                hardware_revisions=?, artifact_version_id=?, revision=?, updated_at=? WHERE project_id=?''',
                (request.boardId, json.dumps(request.componentIds), json.dumps(revisions), saved.id, version, now, project_id))
            conn.execute("UPDATE projects SET name=?, updated_at=? WHERE id=?", (request.name.strip(), now, project_id))
        return self.get(project_id)

    def versions(self, project_id: str) -> list[dict[str, Any]]:
        self.get(project_id)
        with self.connect() as conn:
            rows = conn.execute('''SELECT v.version, v.preview_json, v.checksum, v.created_at,
                v.source_entity_type, s.id AS message_id, m.board_id FROM artifact_versions v
                LEFT JOIN mu_code_metadata m ON m.version_id=v.id
                LEFT JOIN messages s ON s.id=v.source_entity_id AND s.project_id=v.project_id
                WHERE v.artifact_id=? ORDER BY v.version DESC''', (f"mu_code_{project_id}",)).fetchall()
        return [{"revision": row["version"], "code": json.loads(row["preview_json"])["code"],
                 "checksum": row["checksum"], "createdAt": row["created_at"],
                 "source": "ai" if row["source_entity_type"] == 'mu_ai_code' else "saved",
                 **({"messageId": row['message_id']} if row['source_entity_type'] == 'mu_ai_code' and row['message_id'] else {}),
                 **({"boardId": row["board_id"]} if row["board_id"] else {})} for row in rows]

    def record_ai_code(self, project_id: str, board_id: str, message_id: str, reply: str) -> None:
        code = reply_code(reply)
        if code is None:
            return
        if len(code.encode('utf-8')) > 65_536 or '\x00' in code:
            return
        with self.lock:
            self.get(project_id)
            artifact_id = f'mu_code_{project_id}'
            with self.connect() as conn:
                if conn.execute('SELECT 1 FROM artifact_versions WHERE artifact_id=? AND source_entity_id=?', (artifact_id, message_id)).fetchone():
                    return
                revision = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifact_versions WHERE artifact_id=?', (artifact_id,)).fetchone()[0]
            saved = self.artifacts.upsert_text_artifact(
                artifact_id=artifact_id, project_id=project_id, title='main.py', kind=ArtifactKind.CODE,
                status=ArtifactStatus.NEEDS_REVIEW, source_agent_id='mu-ai', source_entity_type='mu_ai_code',
                source_entity_id=message_id, source_version=revision, content=code,
                summary='AI生成的待接受代码，未保存为当前程序、未上传或运行。', mime_type='text/x-python', language='python',
            )
            with self.connect() as conn:
                conn.execute('INSERT INTO mu_code_metadata(version_id, board_id) VALUES (?, ?)', (saved.id, board_id))
            # Workspace revision/pointer stays at the last explicitly saved code.

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
        diagnostics.append({"severity": "WARNING", "message": "检查不覆盖 MicroPython 专用 API、实际接线、引脚占用或实物行为，请核对硬件资料。"})
        return {"valid": not any(item["severity"] == "FAIL" for item in diagnostics), "checksum": checksum(request.code), "diagnostics": diagnostics}

    def manifest(self, project_id: str, revision: int) -> dict[str, Any]:
        with self.lock:
            project = self.get(project_id)
            if project["revision"] != revision:
                raise HTTPException(409, "上传版本已变更，请重新保存并核对清单。")
            request = CodeInput(**{key: project[key] for key in ("code", "boardId", "componentIds")})
            if not self.check(request)["valid"]:
                raise HTTPException(422, "代码或硬件检查未通过，不能建立上传清单。")
            revisions = self.hardware_revisions(project["boardId"], project["componentIds"])
            with self.connect() as conn:
                frozen = json.loads(conn.execute("SELECT hardware_revisions FROM mu_workspaces WHERE project_id=?", (project_id,)).fetchone()[0])
            if frozen != revisions:
                raise HTTPException(409, "硬件资料已更新，请核对后保存新版本。")
            return {"projectId": project_id, "revision": revision, "boardId": project["boardId"],
                    "hardwareRevisions": revisions, "files": [{"path": "main.py", "content": project["code"],
                    "sha256": project["checksum"], "size": len(project["code"].encode("utf-8"))}]}
