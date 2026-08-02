"""Tests for ZW-004 clarification and solution services."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from zhangwen.clarification.service import (
    ClarificationRoundModel,
    ClarificationService,
    SolutionDraftModel,
)
from zhangwen.llm.structured import extract_json_object
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.solutions.models import SolutionSection, SolutionSectionChange, SolutionStatus
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import fake_proposal_sections


# ── JSON extraction tests ──


class TestExtractJsonObject:
    def test_direct_json(self):
        data = {"questions": [], "completeness": 50, "message": "test"}
        result = extract_json_object(json.dumps(data))
        assert result == data

    def test_json_in_code_block(self):
        data = {"questions": [], "completeness": 80, "message": "ok"}
        text = f"Here is the result:\n```json\n{json.dumps(data)}\n```\nDone."
        result = extract_json_object(text)
        assert result == data

    def test_json_in_braces(self):
        data = {"sections": [{"id": "s1", "title": "T", "content": "C"}]}
        text = f"Some prefix text {json.dumps(data)} some suffix"
        result = extract_json_object(text)
        assert result == data

    def test_invalid_json_returns_none(self):
        assert extract_json_object("not json at all") is None

    def test_empty_string_returns_none(self):
        assert extract_json_object("") is None


# ── Solution repository tests ──


class TestSolutionRepository:
    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        db_dir = tmp_path / "projects"
        db_dir.mkdir()
        db_file = db_dir / "zhangwen.sqlite3"
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        migrate(conn)
        # Create a test project
        conn.execute(
            """
            INSERT INTO projects
              (id, name, stage, initial_idea, selected_model, created_at, updated_at, last_opened_at)
            VALUES ('prj_test', '测试项目', 'CLARIFYING', '测试创意', 'deepseek-v4-flash',
                    '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO conversations (id, project_id, created_at, updated_at)
            VALUES ('conv_test', 'prj_test', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.commit()
        conn.close()
        return db_file

    def test_create_and_list_solution(self, db_path: Path):
        repo = SolutionRepository(db_path)
        sections = [
            SolutionSection(id="sec_1", title="项目目标", content="测试目标内容"),
            SolutionSection(id="sec_2", title="硬件组成", content="ESP32 x 1"),
        ]
        solution = repo.create_solution("prj_test", sections)
        assert solution.version == 1
        assert solution.status == SolutionStatus.DRAFT
        assert len(solution.sections) == 2

        listed = repo.list_solutions("prj_test")
        assert len(listed) == 1
        assert listed[0].id == solution.id
        assert listed[0].artifactId == "artifact_solution_prj_test"

    def test_version_increment(self, db_path: Path):
        repo = SolutionRepository(db_path)
        sections = [SolutionSection(id="s1", title="T", content="C" * 50)]
        sol1 = repo.create_solution("prj_test", sections)
        sol2 = repo.create_solution("prj_test", sections)
        assert sol1.version == 1
        assert sol2.version == 2
        # First solution should be superseded
        all_sols = repo.list_solutions("prj_test")
        statuses = {s.id: s.status for s in all_sols}
        assert statuses[sol1.id] == SolutionStatus.SUPERSEDED
        assert statuses[sol2.id] == SolutionStatus.DRAFT

    def test_confirm_solution(self, db_path: Path):
        repo = SolutionRepository(db_path)
        sections = [SolutionSection(id="s1", title="T", content="C" * 50)]
        solution = repo.create_solution("prj_test", sections)
        confirmed = repo.confirm_solution("prj_test", solution.id)
        assert confirmed.status == SolutionStatus.CONFIRMED
        assert confirmed.confirmedAt is not None

    def test_get_current_solution(self, db_path: Path):
        repo = SolutionRepository(db_path)
        assert repo.get_current_solution("prj_test") is None
        sections = [SolutionSection(id="s1", title="T", content="C" * 50)]
        repo.create_solution("prj_test", sections)
        current = repo.get_current_solution("prj_test")
        assert current is not None
        assert current.status == SolutionStatus.DRAFT

    def test_confirm_nonexistent_raises(self, db_path: Path):
        repo = SolutionRepository(db_path)
        with pytest.raises(ValueError, match="方案不存在"):
            repo.confirm_solution("prj_test", "sol_nonexistent")

    def test_revise_solution_changes_only_target_sections_and_records_revision(self, db_path: Path):
        repo = SolutionRepository(db_path)
        base = repo.create_solution(
            "prj_test",
            [
                SolutionSection(id="goal", title="项目目标", content="制作桌面饮水提醒器。"),
                SolutionSection(id="functional_logic", title="功能逻辑", content="蜂鸣器声音提醒，按键后记录。"),
                SolutionSection(id="hardware", title="硬件方案", content="ESP32、蜂鸣器、OLED、RTC、USB 供电。"),
                SolutionSection(id="software", title="软件模块", content="提醒调度、显示、记录。"),
                SolutionSection(id="structure", title="结构建议", content="桌面小盒。"),
            ],
        )

        revised, revision = repo.create_revision_from_llm(
            "prj_test",
            base=base,
            revised_sections=[
                SolutionSection(id="goal", title="项目目标", content="制作桌面饮水提醒器。"),
                SolutionSection(id="functional_logic", title="功能逻辑", content="RGB LED 灯光提醒，按键后记录。"),
                SolutionSection(id="hardware", title="硬件方案", content="ESP32、RGB LED、OLED、RTC、USB 供电。"),
                SolutionSection(id="software", title="软件模块", content="提醒调度、显示、记录。"),
                SolutionSection(id="structure", title="结构建议", content="桌面小盒。"),
            ],
            user_request="把声音提醒改为灯光提醒",
            changed_sections=[
                SolutionSectionChange(
                    sectionId="functional_logic",
                    sectionTitle="功能逻辑",
                    changeType="updated",
                    before="蜂鸣器声音提醒，按键后记录。",
                    after="RGB LED 灯光提醒，按键后记录。",
                    reason="LLM 根据用户要求把提醒方式改为灯光。",
                ),
                SolutionSectionChange(
                    sectionId="hardware",
                    sectionTitle="硬件方案",
                    changeType="updated",
                    before="ESP32、蜂鸣器、OLED、RTC、USB 供电。",
                    after="ESP32、RGB LED、OLED、RTC、USB 供电。",
                    reason="LLM 根据提醒方式替换执行器。",
                ),
            ],
            preserved_sections=["项目目标", "软件模块", "结构建议"],
            impact_summary=["蜂鸣器声音提醒 → RGB LED 灯光提醒"],
        )

        assert revised.version == 2
        assert revised.basedOnVersion == base.version
        assert revised.status == SolutionStatus.DRAFT
        assert revision.baseSolutionId == base.id
        assert revision.newSolutionId == revised.id
        assert {change.sectionId for change in revision.changedSections} == {
            "functional_logic",
            "hardware",
        }
        assert "软件模块" in revision.preservedSections
        assert next(section for section in revised.sections if section.id == "software").content == "提醒调度、显示、记录。"
        assert "RGB LED" in next(section for section in revised.sections if section.id == "hardware").content
        assert any("蜂鸣器声音提醒" in item for item in revision.impactSummary)

        original = repo.get_solution("prj_test", base.id)
        assert original.id == base.id
        assert original.version == 1

    def test_solution_artifact_tracks_latest_version(self, db_path: Path):
        repo = SolutionRepository(db_path)
        sol1 = repo.create_solution(
            "prj_test",
            [SolutionSection(id="goal", title="项目目标", content="v1")],
        )
        sol2, _ = repo.create_revision_from_llm(
            "prj_test",
            base=sol1,
            revised_sections=[SolutionSection(id="goal", title="项目目标", content="v2")],
            user_request="使用 LLM 修订方案",
            changed_sections=[
                SolutionSectionChange(
                    sectionId="goal",
                    sectionTitle="项目目标",
                    changeType="updated",
                    before="v1",
                    after="v2",
                    reason="LLM 输出新目标。",
                )
            ],
            preserved_sections=[],
            impact_summary=["目标内容更新"],
        )
        artifact = ArtifactRepository(db_path).get_artifact("prj_test", "artifact_solution_prj_test")

        assert sol1.artifactId == artifact.id
        assert sol2.artifactVersionId == artifact.currentVersionId
        assert [version.version for version in artifact.versions] == [2, 1]
        assert artifact.title == "推荐实现方案"

    def test_revising_solution_marks_existing_proposal_stale_without_creating_new_one(self, db_path: Path):
        sol_repo = SolutionRepository(db_path)
        proposal_repo = ProposalRepository(db_path)
        solution = sol_repo.create_solution(
            "prj_test",
            [SolutionSection(id="goal", title="项目目标", content="v1")],
        )
        confirmed = sol_repo.confirm_solution("prj_test", solution.id)
        proposal = proposal_repo.create_from_solution(
            "prj_test",
            confirmed,
            fake_proposal_sections(),
        )
        approved = proposal_repo.confirm_proposal("prj_test", proposal.id)

        sol_repo.create_revision_from_llm(
            "prj_test",
            base=confirmed,
            revised_sections=[SolutionSection(id="goal", title="项目目标", content="v2")],
            user_request="使用 LLM 修订方案",
            changed_sections=[
                SolutionSectionChange(
                    sectionId="goal",
                    sectionTitle="项目目标",
                    changeType="updated",
                    before="v1",
                    after="v2",
                    reason="LLM 输出新目标。",
                )
            ],
            preserved_sections=[],
            impact_summary=["目标内容更新"],
        )
        proposal_repo.mark_project_proposals_stale(
            "prj_test",
            "推荐实现方案已修订，立项书需在确认新方案后更新。",
        )

        proposals = proposal_repo.list_proposals("prj_test")
        assert len(proposals) == 1
        assert proposals[0].id == approved.id
        assert proposals[0].status == "STALE"


# ── Migration tests ──


class TestMigrations:
    def test_schema_version_is_16(self):
        assert CURRENT_SCHEMA_VERSION == 31

    def test_v2_creates_solutions_table(self, tmp_path: Path):
        db_file = tmp_path / "test.sqlite3"
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        migrate(conn)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "solutions" in tables
        assert "clarification_rounds" in tables
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == CURRENT_SCHEMA_VERSION
        conn.close()

    def test_reject_future_version(self, tmp_path: Path):
        db_file = tmp_path / "test.sqlite3"
        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA user_version=99")
        conn.commit()
        from zhangwen.projects.errors import UnsupportedProjectSchemaError
        with pytest.raises(UnsupportedProjectSchemaError):
            migrate(conn)
        conn.close()
