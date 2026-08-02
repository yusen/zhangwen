"""Local validation and fixed-path packaging for model-generated lessons."""

from __future__ import annotations

import re
from dataclasses import dataclass

from zhangwen.lesson_agent.models import LessonContentDraft, LessonDocumentKind


@dataclass(frozen=True)
class GeneratedLessonFile:
    kind: LessonDocumentKind
    title: str
    path: str
    mime_type: str
    content: str


@dataclass(frozen=True)
class GeneratedLesson:
    grade_band: str
    lesson_hours: int
    files: list[GeneratedLessonFile]


def validate_and_package_lesson(
    *,
    draft: LessonContentDraft,
    grade_band: str,
    lesson_hours: int,
) -> GeneratedLesson:
    files = [
        GeneratedLessonFile(
            LessonDocumentKind.TEACHER_GUIDE,
            "教师教案",
            "lesson/teacher_guide.md",
            "text/markdown",
            draft.teacherGuide,
        ),
        GeneratedLessonFile(
            LessonDocumentKind.STUDENT_WORKSHEET,
            "学生任务单",
            "lesson/student_worksheet.md",
            "text/markdown",
            draft.studentWorksheet,
        ),
        GeneratedLessonFile(
            LessonDocumentKind.RUBRIC,
            "评价量表",
            "lesson/rubric.md",
            "text/markdown",
            draft.rubric,
        ),
        GeneratedLessonFile(
            LessonDocumentKind.SAFETY_NOTES,
            "安全说明",
            "lesson/safety_notes.md",
            "text/markdown",
            draft.safetyNotes,
        ),
    ]
    _validate_documents(files)
    return GeneratedLesson(
        grade_band=grade_band,
        lesson_hours=lesson_hours,
        files=files,
    )


def normalize_grade_band(value: str | None) -> str:
    cleaned = (value or "初中").strip()
    return cleaned[:40] if cleaned else "初中"


def normalize_lesson_hours(value: int | None) -> int:
    return 2 if value is None else max(1, min(8, int(value)))


def _validate_documents(files: list[GeneratedLessonFile]) -> None:
    required_markers = {
        LessonDocumentKind.TEACHER_GUIDE: ("学习目标", "教学"),
        LessonDocumentKind.STUDENT_WORKSHEET: ("任务",),
        LessonDocumentKind.RUBRIC: ("评价",),
        LessonDocumentKind.SAFETY_NOTES: ("安全说明", "供电"),
    }
    forbidden_patterns = {
        r"sk-[A-Za-z0-9_-]{8,}": "疑似 API Key",
        r"(?i)(api[_-]?key|access[_-]?token|wifi[_-]?password)\s*[:=]\s*['\"]?[^\s'\"]+": "硬编码凭据",
        r"(?i)authorization\s*:\s*bearer": "Authorization 头",
        r"(?i)\bCOM\d+\b": "真实串口标识",
        r"(?i)[A-Z]:\\Users\\[^\\\s]+": "本机绝对路径",
    }
    for file in files:
        if any(marker not in file.content for marker in required_markers[file.kind]):
            raise ValueError(f"{file.title} 缺少必需章节。")
        for pattern, label in forbidden_patterns.items():
            if re.search(pattern, file.content):
                raise ValueError(f"{file.title} 包含禁止内容：{label}。")
