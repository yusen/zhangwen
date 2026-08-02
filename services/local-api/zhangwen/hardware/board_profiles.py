"""Markdown BoardProfile catalog with data-directory overlays."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from zhangwen.hardware.board_skills import (
    BoardSkillRepository,
    BoardSkillSummary,
    BoardSkillValidationError,
)


BUNDLED_BOARD_PROFILE_DIR = Path(__file__).resolve().parent / "board-profiles"
MAX_BOARD_PROFILE_CHARS = 60_000
_FRONTMATTER_FIELDS = {"id", "name", "aliases", "platform", "language"}


class BoardProfileSummary(BaseModel):
    id: str
    displayName: str
    aliases: list[str] = Field(default_factory=list)
    platform: str
    language: Literal["micropython"] = "micropython"
    overridden: bool
    revision: str
    skillPackage: BoardSkillSummary | None = None


class BoardProfile(BoardProfileSummary):
    content: str


class BoardProfileListResponse(BaseModel):
    profiles: list[BoardProfileSummary]


class BoardProfileResponse(BaseModel):
    profile: BoardProfile


class UpdateBoardProfileRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_BOARD_PROFILE_CHARS)
    expectedRevision: str = Field(min_length=8, max_length=128)


class ResetBoardProfileRequest(BaseModel):
    expectedRevision: str = Field(min_length=8, max_length=128)


class BoardProfileError(ValueError):
    pass


class BoardProfileNotFoundError(BoardProfileError):
    pass


class BoardProfileConflictError(BoardProfileError):
    pass


class BoardProfileValidationError(BoardProfileError):
    pass


class BoardProfileRepository:
    def __init__(self, data_dir: Path) -> None:
        self._overlay_dir = Path(data_dir) / "board-profiles"

    def list_profiles(self) -> list[BoardProfileSummary]:
        return [
            BoardProfileSummary.model_validate(self.get_profile(profile_id))
            for profile_id in self._profile_ids()
        ]

    def get_profile(self, profile_id: str) -> BoardProfile:
        normalized = _normalize_profile_id(profile_id)
        bundled = BUNDLED_BOARD_PROFILE_DIR / f"{normalized}.md"
        if not bundled.is_file():
            raise BoardProfileNotFoundError("开发板档案不存在。")
        overlay = self._overlay_dir / f"{normalized}.md"
        source = overlay if overlay.is_file() else bundled
        content = source.read_text(encoding="utf-8")
        metadata = parse_board_profile_frontmatter(content, expected_id=normalized)
        try:
            skill_package = BoardSkillRepository().summary_for_profile(normalized)
        except BoardSkillValidationError as exc:
            raise BoardProfileValidationError(f"开发板 Skill 包无效：{exc}") from exc
        return BoardProfile(
            id=normalized,
            displayName=metadata["name"],
            aliases=_split_aliases(metadata["aliases"]),
            platform=metadata["platform"],
            language="micropython",
            overridden=source == overlay,
            revision=_revision(content),
            skillPackage=skill_package,
            content=content,
        )

    def search(self, query: str, *, limit: int = 3) -> list[BoardProfile]:
        terms = _query_terms(query)
        if not terms:
            return []
        ranked: list[tuple[int, BoardProfile]] = []
        for profile_id in self._profile_ids():
            profile = self.get_profile(profile_id)
            identity = " ".join(
                [profile.id, profile.displayName, *profile.aliases]
            ).lower()
            score = sum(8 if term in profile.id else 4 for term in terms if term in identity)
            if score:
                ranked.append((score, profile))
        ranked.sort(key=lambda item: (-item[0], item[1].displayName))
        return [profile for _, profile in ranked[:limit]]

    def update_profile(
        self,
        profile_id: str,
        *,
        content: str,
        expected_revision: str,
    ) -> BoardProfile:
        current = self.get_profile(profile_id)
        self._check_revision(current.revision, expected_revision)
        parse_board_profile_frontmatter(content, expected_id=current.id)
        self._overlay_dir.mkdir(parents=True, exist_ok=True)
        target = self._overlay_dir / f"{current.id}.md"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        return self.get_profile(current.id)

    def reset_profile(self, profile_id: str, *, expected_revision: str) -> BoardProfile:
        current = self.get_profile(profile_id)
        self._check_revision(current.revision, expected_revision)
        target = self._overlay_dir / f"{current.id}.md"
        if target.is_file():
            target.unlink()
        return self.get_profile(current.id)

    def _profile_ids(self) -> list[str]:
        return sorted(path.stem for path in BUNDLED_BOARD_PROFILE_DIR.glob("*.md"))

    @staticmethod
    def _check_revision(current: str, expected: str) -> None:
        if current != expected:
            raise BoardProfileConflictError("开发板档案已被其他操作更新，请刷新后重试。")


def parse_board_profile_frontmatter(
    content: str,
    *,
    expected_id: str | None = None,
) -> dict[str, str]:
    if len(content) > MAX_BOARD_PROFILE_CHARS:
        raise BoardProfileValidationError("开发板档案超过允许上限。")
    if "\x00" in content:
        raise BoardProfileValidationError("开发板档案不能包含 NUL 字符。")
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise BoardProfileValidationError("BoardProfile 必须以 frontmatter 开始。")
    try:
        closing = next(index for index, line in enumerate(lines[1:20], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise BoardProfileValidationError("BoardProfile frontmatter 未闭合。") from exc
    values: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        if ":" not in line:
            raise BoardProfileValidationError("BoardProfile frontmatter 必须使用 key: value。")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if key not in _FRONTMATTER_FIELDS or key in values or not value:
            raise BoardProfileValidationError("BoardProfile frontmatter 字段无效或重复。")
        values[key] = value
    if set(values) != _FRONTMATTER_FIELDS:
        raise BoardProfileValidationError("BoardProfile 缺少必需 frontmatter 字段。")
    profile_id = _normalize_profile_id(values["id"])
    if expected_id and profile_id != expected_id:
        raise BoardProfileValidationError(f"BoardProfile id 必须保持为 {expected_id}。")
    if values["language"].lower() != "micropython":
        raise BoardProfileValidationError("当前 BoardProfile 只支持 MicroPython。")
    if not _split_aliases(values["aliases"]):
        raise BoardProfileValidationError("BoardProfile 至少需要一个别名。")
    if not "\n".join(lines[closing + 1 :]).strip():
        raise BoardProfileValidationError("BoardProfile 正文不能为空。")
    values["id"] = profile_id
    values["language"] = "micropython"
    return values


def _normalize_profile_id(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
        raise BoardProfileValidationError("BoardProfile id 必须使用小写字母、数字和连字符。")
    return normalized


def _split_aliases(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _query_terms(query: str) -> set[str]:
    normalized = query.lower()[:1000]
    terms = {
        match.group(0)
        for match in re.finditer(r"[a-z0-9][a-z0-9.+_-]{1,31}", normalized)
    }
    for keyword in ("行空板", "开发板", "主控"):
        if keyword in normalized:
            terms.add(keyword)
    return terms


def _revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]
