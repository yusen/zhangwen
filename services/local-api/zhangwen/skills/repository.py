"""SQLite repository for user-defined skills."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.skills.models import (
    JsonSchemaObject,
    SkillConfirmationPolicy,
    SkillDefinition,
    SkillOrigin,
    SkillPermission,
    SkillRiskLevel,
    RetryPolicy,
    TimeoutPolicy,
)
from zhangwen.projects.models import ExpertType
from zhangwen.skills.registry import built_in_skills


class SkillRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._override_path = db_path.with_name("skill-description-overrides.json")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def list_skills(self) -> list[SkillDefinition]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_skills ORDER BY updated_at DESC"
            ).fetchall()
        overrides = self._load_overrides()
        return [
            _apply_override(skill, overrides.get(skill.id))
            for skill in built_in_skills() + [_to_skill(row) for row in rows]
        ]

    def create_user_skill(
        self,
        *,
        name: str,
        description: str,
        input_schema: JsonSchemaObject | None,
        output_schema: JsonSchemaObject | None,
        permissions: list[SkillPermission],
        owner_expert: ExpertType = ExpertType.PROBLEM_GUIDE,
    ) -> SkillDefinition:
        now = _now()
        skill_id = _id("skill_user")
        safe_permissions = _normalize_permissions(permissions)
        skill = SkillDefinition(
            id=skill_id,
            name=name.strip(),
            description=description.strip(),
            origin=SkillOrigin.USER,
            enabled=True,
            ownerExpert=owner_expert,
            inputSchema=input_schema or JsonSchemaObject(type="object"),
            outputSchema=output_schema or JsonSchemaObject(type="object"),
            requiredTools=[],
            riskLevel=SkillRiskLevel.LOW,
            confirmationPolicy=SkillConfirmationPolicy.NEVER,
            timeoutPolicy=TimeoutPolicy(),
            retryPolicy=RetryPolicy(),
            artifactTypes=[],
            permissions=safe_permissions,
            createdAt=now,
            updatedAt=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_skills (
                  id, name, description, enabled, input_schema_json,
                  output_schema_json, permissions_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill.id,
                    skill.name,
                    skill.description,
                    1,
                    json.dumps(skill.inputSchema.model_dump(mode="json"), ensure_ascii=False),
                    json.dumps(skill.outputSchema.model_dump(mode="json"), ensure_ascii=False),
                    json.dumps([p.value for p in safe_permissions], ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return skill

    def update_skill(
        self,
        skill_id: str,
        *,
        name: str | None,
        description: str | None,
        enabled: bool | None,
        permissions: list[SkillPermission] | None,
    ) -> SkillDefinition:
        built_in = next((skill for skill in built_in_skills() if skill.id == skill_id), None)
        if built_in is not None:
            overrides = self._load_overrides()
            current = overrides.get(skill_id, {})
            overrides[skill_id] = {
                **current,
                **({"name": name.strip()} if name is not None else {}),
                **({"description": description.strip()} if description is not None else {}),
                **({"enabled": enabled} if enabled is not None else {}),
            }
            self._save_overrides(overrides)
            return _apply_override(built_in, overrides[skill_id])

        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_skills WHERE id = ?",
                (skill_id,),
            ).fetchone()
            if row is None:
                raise ValueError("用户 Skill 不存在。")
            next_name = str(row["name"]) if name is None else name.strip()
            next_description = (
                str(row["description"]) if description is None else description.strip()
            )
            next_enabled = bool(row["enabled"]) if enabled is None else enabled
            current_permissions = [
                SkillPermission(item) for item in json.loads(row["permissions_json"])
            ]
            next_permissions = (
                current_permissions
                if permissions is None
                else _normalize_permissions(permissions)
            )
            conn.execute(
                """
                UPDATE user_skills
                SET name = ?, description = ?, enabled = ?, permissions_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_name,
                    next_description,
                    1 if next_enabled else 0,
                    json.dumps([p.value for p in next_permissions], ensure_ascii=False),
                    now,
                    skill_id,
                ),
            )
            updated = conn.execute(
                "SELECT * FROM user_skills WHERE id = ?",
                (skill_id,),
            ).fetchone()
        return _to_skill(updated)

    def _load_overrides(self) -> dict[str, dict[str, object]]:
        if not self._override_path.exists():
            return {}
        try:
            loaded = json.loads(self._override_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _save_overrides(self, overrides: dict[str, dict[str, object]]) -> None:
        self._override_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._override_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._override_path)


def _normalize_permissions(
    permissions: list[SkillPermission],
) -> list[SkillPermission]:
    unique = list(dict.fromkeys(permissions))
    return unique


def _to_skill(row: sqlite3.Row) -> SkillDefinition:
    return SkillDefinition(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        origin=SkillOrigin.USER,
        enabled=bool(row["enabled"]),
        ownerExpert=ExpertType.PROBLEM_GUIDE,
        inputSchema=JsonSchemaObject(**json.loads(row["input_schema_json"])),
        outputSchema=JsonSchemaObject(**json.loads(row["output_schema_json"])),
        requiredTools=[],
        riskLevel=SkillRiskLevel.LOW,
        confirmationPolicy=SkillConfirmationPolicy.NEVER,
        timeoutPolicy=TimeoutPolicy(),
        retryPolicy=RetryPolicy(),
        artifactTypes=[],
        permissions=[SkillPermission(item) for item in json.loads(row["permissions_json"])],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _apply_override(
    skill: SkillDefinition,
    override: dict[str, object] | None,
) -> SkillDefinition:
    if not override:
        return skill
    values = skill.model_dump()
    if isinstance(override.get("name"), str):
        values["name"] = str(override["name"])
    if isinstance(override.get("description"), str):
        values["description"] = str(override["description"])
    if isinstance(override.get("enabled"), bool):
        values["enabled"] = bool(override["enabled"])
    values["updatedAt"] = _now()
    return SkillDefinition.model_validate(values)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
