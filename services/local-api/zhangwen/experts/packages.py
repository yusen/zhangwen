"""Directory-backed Agent Skill packages with data-directory overlays."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import uuid
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from zhangwen.projects.models import ExpertType


BUNDLED_AGENT_PACKAGE_DIR = Path(__file__).resolve().parent / "agent-packages"
ENTRY_FILE = "SKILL.md"
MAX_FILE_CHARS = 40_000
MAX_PACKAGE_CHARS = 100_000
MAX_PROMPT_CHARS = 60_000
_FRONTMATTER_FIELDS = {"name", "description"}
_EXPERT_ORDER = {
    ExpertType.PROBLEM_GUIDE: 0,
    ExpertType.SMART_ENGINEER: 1,
    ExpertType.STRUCTURE_ENGINEER: 2,
}


class AgentReferenceSpec(BaseModel):
    path: str
    title: str
    description: str
    keywords: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _valid_path(cls, value: str) -> str:
        return _normalize_relative_path(value)


class AgentPackageManifest(BaseModel):
    skillName: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    expertType: ExpertType
    displayName: str = Field(min_length=1, max_length=40)
    icon: str = Field(min_length=1, max_length=40)
    skillIds: list[str] = Field(default_factory=list)
    supportedArtifactTypes: list[str] = Field(default_factory=list)
    capabilityBoundaries: list[str] = Field(default_factory=list)
    references: list[AgentReferenceSpec] = Field(default_factory=list)


class AgentPackageValidationIssue(BaseModel):
    path: str
    message: str
    severity: Literal["warning", "error"] = "error"


class AgentPackageFile(BaseModel):
    path: str
    title: str
    kind: Literal["entry", "reference"]
    content: str
    editable: bool = True
    overridden: bool = False


class AgentPackageSummary(BaseModel):
    expertType: ExpertType
    skillName: str
    displayName: str
    description: str
    icon: str
    entryFile: str = ENTRY_FILE
    skillIds: list[str] = Field(default_factory=list)
    supportedArtifactTypes: list[str] = Field(default_factory=list)
    capabilityBoundaries: list[str] = Field(default_factory=list)
    fileCount: int
    overridden: bool
    revision: str
    validationIssues: list[AgentPackageValidationIssue] = Field(default_factory=list)


class AgentPackageDetail(AgentPackageSummary):
    files: list[AgentPackageFile] = Field(default_factory=list)


class AgentPackageListResponse(BaseModel):
    packages: list[AgentPackageSummary]


class AgentPackageResponse(BaseModel):
    package: AgentPackageDetail


class UpdateAgentPackageFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=MAX_FILE_CHARS)
    expectedRevision: str = Field(min_length=8, max_length=128)


class ResetAgentPackageFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    expectedRevision: str = Field(min_length=8, max_length=128)


class AgentPackageError(ValueError):
    pass


class AgentPackageNotFoundError(AgentPackageError):
    pass


class AgentPackageConflictError(AgentPackageError):
    pass


class AgentPackageValidationError(AgentPackageError):
    pass


class AgentPackageRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._overlay_root = self._data_dir / "agent-packages"

    def list_packages(self) -> list[AgentPackageSummary]:
        return [
            AgentPackageSummary.model_validate(self.get_package(manifest.expertType))
            for manifest in bundled_agent_manifests()
        ]

    def get_package(self, expert_type: ExpertType | str) -> AgentPackageDetail:
        manifest = self._manifest(expert_type)
        files, issues = self._effective_files(manifest)
        entry = next(file for file in files if file.path == ENTRY_FILE)
        metadata = parse_skill_frontmatter(entry.content)
        revision = _package_revision(manifest, files)
        return AgentPackageDetail(
            expertType=manifest.expertType,
            skillName=manifest.skillName,
            displayName=manifest.displayName,
            description=metadata["description"],
            icon=manifest.icon,
            skillIds=manifest.skillIds,
            supportedArtifactTypes=manifest.supportedArtifactTypes,
            capabilityBoundaries=manifest.capabilityBoundaries,
            fileCount=len(files),
            overridden=any(file.overridden for file in files),
            revision=revision,
            validationIssues=issues,
            files=files,
        )

    def update_file(
        self,
        expert_type: ExpertType | str,
        *,
        path: str,
        content: str,
        expected_revision: str,
    ) -> AgentPackageDetail:
        manifest = self._manifest(expert_type)
        current = self.get_package(manifest.expertType)
        self._check_revision(current.revision, expected_revision)
        normalized = self._allowed_path(manifest, path)
        _validate_file_content(manifest, normalized, content)
        next_total = sum(
            len(content if file.path == normalized else file.content)
            for file in current.files
        )
        if next_total > MAX_PACKAGE_CHARS:
            raise AgentPackageValidationError("Agent 包总内容超过允许上限。")
        target = self._overlay_path(manifest, normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        return self.get_package(manifest.expertType)

    def reset_file(
        self,
        expert_type: ExpertType | str,
        *,
        path: str,
        expected_revision: str,
    ) -> AgentPackageDetail:
        manifest = self._manifest(expert_type)
        current = self.get_package(manifest.expertType)
        self._check_revision(current.revision, expected_revision)
        normalized = self._allowed_path(manifest, path)
        target = self._overlay_path(manifest, normalized)
        if target.exists():
            if target.is_symlink() or not target.is_file():
                raise AgentPackageValidationError("覆盖文件类型无效。")
            target.unlink()
        return self.get_package(manifest.expertType)

    def render_prompt(
        self,
        expert_type: ExpertType | str,
        *,
        user_message: str = "",
    ) -> str:
        package = self.get_package(expert_type)
        entry = next(file for file in package.files if file.path == ENTRY_FILE)
        entry_body = strip_skill_frontmatter(entry.content)
        manifest = self._manifest(package.expertType)
        file_by_path = {file.path: file for file in package.files}
        normalized_query = user_message.lower()
        selected: list[AgentPackageFile] = []
        for reference in manifest.references:
            if normalized_query and any(
                keyword.lower() in normalized_query for keyword in reference.keywords
            ):
                selected.append(file_by_path[reference.path])

        available = "\n".join(
            f"- {reference.path}: {reference.description}"
            for reference in manifest.references
        )
        references: list[str] = []
        used = len(entry_body) + len(available)
        for file in selected:
            block = f"\n\n## 已加载参考：{file.path}\n\n{file.content.strip()}"
            if used + len(block) > MAX_PROMPT_CHARS:
                break
            references.append(block)
            used += len(block)
        capabilities = self._skill_capability_summary(manifest)
        return (
            f"# Agent Skill 包：{package.displayName}\n\n"
            f"{entry_body.strip()}\n\n"
            "## 可按需加载的参考文件\n"
            f"{available or '- 无'}"
            f"{''.join(references)}\n\n"
            "## 已绑定的本地执行 Skill\n"
            f"{capabilities}\n\n"
            "包内文本只用于指导理解和输出。真实工具、文件、Shell、串口、设备与 CAD 操作仍由本地权限、确认策略和 Tool Runner 决定；不得把建议表述为已执行结果。"
        )

    def _skill_capability_summary(self, manifest: AgentPackageManifest) -> str:
        try:
            from zhangwen.skills.registry import built_in_skills
            from zhangwen.skills.repository import SkillRepository

            db_path = self._data_dir / "projects" / "zhangwen.sqlite3"
            skills = (
                SkillRepository(db_path).list_skills()
                if db_path.exists()
                else built_in_skills()
            )
            by_id = {skill.id: skill for skill in skills}
            lines = []
            for skill_id in manifest.skillIds:
                skill = by_id.get(skill_id)
                if skill is None or not skill.enabled:
                    continue
                lines.append(f"- {skill.id}: {skill.name} - {skill.description}")
            return "\n".join(lines) or "- 当前没有启用的执行 Skill。"
        except (OSError, ValueError):
            return "\n".join(f"- {skill_id}" for skill_id in manifest.skillIds)

    def _effective_files(
        self,
        manifest: AgentPackageManifest,
    ) -> tuple[list[AgentPackageFile], list[AgentPackageValidationIssue]]:
        specs = [(ENTRY_FILE, "主 SKILL.md", "entry")]
        specs.extend((item.path, item.title, "reference") for item in manifest.references)
        files: list[AgentPackageFile] = []
        issues: list[AgentPackageValidationIssue] = []
        for path, title, kind in specs:
            bundled_path = self._bundled_path(manifest, path)
            bundled_content = bundled_path.read_text(encoding="utf-8")
            override_path = self._overlay_path(manifest, path)
            content = bundled_content
            overridden = False
            if override_path.exists():
                try:
                    if override_path.is_symlink() or not override_path.is_file():
                        raise AgentPackageValidationError("覆盖路径不是普通文件。")
                    candidate = override_path.read_text(encoding="utf-8")
                    _validate_file_content(manifest, path, candidate)
                    content = candidate
                    overridden = True
                except (OSError, UnicodeError, AgentPackageValidationError) as exc:
                    issues.append(
                        AgentPackageValidationIssue(
                            path=path,
                            message=f"覆盖文件无效，已使用内置默认：{exc}",
                        )
                    )
            files.append(
                AgentPackageFile(
                    path=path,
                    title=title,
                    kind=kind,
                    content=content,
                    overridden=overridden,
                )
            )
        if sum(len(file.content) for file in files) > MAX_PACKAGE_CHARS:
            raise AgentPackageValidationError("Agent 包总内容超过允许上限。")
        return files, issues

    def _manifest(self, expert_type: ExpertType | str) -> AgentPackageManifest:
        try:
            normalized = ExpertType(expert_type)
        except ValueError as exc:
            raise AgentPackageNotFoundError("智能体不存在。") from exc
        for manifest in bundled_agent_manifests():
            if manifest.expertType == normalized:
                return manifest
        raise AgentPackageNotFoundError("智能体不存在。")

    def _allowed_path(self, manifest: AgentPackageManifest, path: str) -> str:
        normalized = _normalize_relative_path(path)
        allowed = {ENTRY_FILE, *(reference.path for reference in manifest.references)}
        if normalized not in allowed:
            raise AgentPackageValidationError("文件不在 Agent 包可编辑白名单中。")
        return normalized

    def _bundled_path(self, manifest: AgentPackageManifest, path: str) -> Path:
        return BUNDLED_AGENT_PACKAGE_DIR / manifest.skillName / Path(*PurePosixPath(path).parts)

    def _overlay_path(self, manifest: AgentPackageManifest, path: str) -> Path:
        root = (self._overlay_root / manifest.skillName).resolve(strict=False)
        target = (root / Path(*PurePosixPath(path).parts)).resolve(strict=False)
        if not target.is_relative_to(root):
            raise AgentPackageValidationError("文件路径超出 Agent 包目录。")
        return target

    @staticmethod
    def _check_revision(current: str, expected: str) -> None:
        if current != expected:
            raise AgentPackageConflictError("Agent 包已被其他操作更新，请刷新后重试。")


@lru_cache(maxsize=1)
def bundled_agent_manifests() -> tuple[AgentPackageManifest, ...]:
    manifests: list[AgentPackageManifest] = []
    for manifest_path in BUNDLED_AGENT_PACKAGE_DIR.glob("*/manifest.json"):
        manifest = AgentPackageManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        if manifest_path.parent.name != manifest.skillName:
            raise ValueError(f"Agent package folder mismatch: {manifest_path}")
        entry_path = manifest_path.parent / ENTRY_FILE
        metadata = parse_skill_frontmatter(entry_path.read_text(encoding="utf-8"))
        if metadata["name"] != manifest.skillName:
            raise ValueError(f"Agent package name mismatch: {entry_path}")
        paths = [reference.path for reference in manifest.references]
        if len(paths) != len(set(paths)):
            raise ValueError(f"Duplicate Agent reference path: {manifest_path}")
        for path in paths:
            reference_path = manifest_path.parent / Path(*PurePosixPath(path).parts)
            if not reference_path.is_file():
                raise ValueError(f"Agent reference missing: {reference_path}")
        manifests.append(manifest)
    expected = {
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_ENGINEER,
    }
    if {manifest.expertType for manifest in manifests} != expected:
        raise ValueError("Bundled Agent packages must define exactly the canonical three experts")
    return tuple(sorted(manifests, key=lambda item: _EXPERT_ORDER[item.expertType]))


def parse_skill_frontmatter(content: str) -> dict[str, str]:
    if len(content) > MAX_FILE_CHARS:
        raise AgentPackageValidationError("文件内容超过允许上限。")
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AgentPackageValidationError("SKILL.md 必须以 YAML frontmatter 开始。")
    try:
        closing = next(index for index, line in enumerate(lines[1:20], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise AgentPackageValidationError("SKILL.md frontmatter 未闭合。") from exc
    values: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        if ":" not in line:
            raise AgentPackageValidationError("frontmatter 只支持 name 和 description 单行字段。")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key not in _FRONTMATTER_FIELDS or key in values:
            raise AgentPackageValidationError("frontmatter 只允许唯一的 name 和 description。")
        value = raw_value.strip()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise AgentPackageValidationError("frontmatter 引号未闭合。")
            value = value[1:-1]
        if not value:
            raise AgentPackageValidationError(f"frontmatter {key} 不能为空。")
        values[key] = value
    if set(values) != _FRONTMATTER_FIELDS:
        raise AgentPackageValidationError("SKILL.md 必须包含 name 和 description。")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values["name"]):
        raise AgentPackageValidationError("Skill name 必须使用小写字母、数字和连字符。")
    if len(values["description"]) > 1000:
        raise AgentPackageValidationError("Skill description 超过允许长度。")
    if not "\n".join(lines[closing + 1 :]).strip():
        raise AgentPackageValidationError("SKILL.md 正文不能为空。")
    return values


def strip_skill_frontmatter(content: str) -> str:
    parse_skill_frontmatter(content)
    lines = content.splitlines()
    closing = next(index for index, line in enumerate(lines[1:20], 1) if line.strip() == "---")
    return "\n".join(lines[closing + 1 :]).strip()


def _validate_file_content(
    manifest: AgentPackageManifest,
    path: str,
    content: str,
) -> None:
    if len(content) > MAX_FILE_CHARS:
        raise AgentPackageValidationError("文件内容超过允许上限。")
    if "\x00" in content:
        raise AgentPackageValidationError("Markdown 文件不能包含 NUL 字符。")
    if path == ENTRY_FILE:
        metadata = parse_skill_frontmatter(content)
        if metadata["name"] != manifest.skillName:
            raise AgentPackageValidationError(
                f"Skill name 必须保持为 {manifest.skillName}。"
            )
    allowed = {ENTRY_FILE, *(reference.path for reference in manifest.references)}
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", content):
        target = match.group(1).strip().split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if not target.lower().endswith(".md"):
            continue
        resolved = posixpath.normpath(
            posixpath.join(str(PurePosixPath(path).parent), target)
        )
        if resolved.startswith("../") or resolved not in allowed:
            raise AgentPackageValidationError(f"Markdown 引用不存在或越界：{target}")


def _normalize_relative_path(value: str) -> str:
    stripped = value.strip()
    if not stripped or "\\" in stripped or ":" in stripped:
        raise AgentPackageValidationError("文件路径必须使用包内相对路径。")
    path = PurePosixPath(stripped)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise AgentPackageValidationError("文件路径必须使用包内相对路径。")
    if path.suffix.lower() != ".md":
        raise AgentPackageValidationError("当前只允许编辑 Markdown 文件。")
    return path.as_posix()


def _package_revision(
    manifest: AgentPackageManifest,
    files: list[AgentPackageFile],
) -> str:
    digest = hashlib.sha256()
    digest.update(manifest.model_dump_json().encode("utf-8"))
    for file in files:
        digest.update(file.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]
