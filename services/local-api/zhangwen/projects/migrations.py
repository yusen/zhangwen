"""SQLite schema migrations for projects."""

from __future__ import annotations

import sqlite3
import json
import hashlib
import uuid
from datetime import UTC, datetime

from zhangwen.projects.errors import UnsupportedProjectSchemaError

CURRENT_SCHEMA_VERSION = 31


def migrate(conn: sqlite3.Connection) -> None:
    version = _user_version(conn)
    source_version = version
    legacy_context: tuple[
        list[tuple[str, tuple[str, ...]]], str, int
    ] | None = None
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedProjectSchemaError(
            "项目数据库版本高于当前应用支持版本，请升级应用后再打开。"
        )
    if version == 0:
        _create_v1(conn)
        version = 1
    if version < 2:
        _migrate_v2(conn)
    if version < 3:
        _migrate_v3(conn)
        version = 3
    if version < 4:
        _migrate_v4(conn)
        version = 4
    if version < 5:
        _migrate_v5(conn)
        version = 5
    if version < 6:
        _migrate_v6(conn)
        version = 6
    if version < 7:
        _migrate_v7(conn)
        version = 7
    if version < 8:
        _migrate_v8(conn)
        version = 8
    if version < 9:
        _migrate_v9(conn)
        version = 9
    if version < 10:
        _migrate_v10(conn)
        version = 10
    if version < 11:
        _migrate_v11(conn)
        version = 11
    if version < 12:
        _migrate_v12(conn)
        version = 12
    if version < 13:
        _migrate_v13(conn)
        version = 13
    if version < 14:
        _migrate_v14(conn)
        version = 14
    if version < 15:
        _migrate_v15(conn)
        version = 15
    if version < 16:
        _migrate_v16(conn)
        version = 16
    if version < 17:
        _migrate_v17(conn)
        version = 17
    if version < 18:
        _migrate_v18(conn)
        version = 18
    if version < 19:
        _migrate_v19(conn)
        version = 19
    if version < 20:
        _migrate_v20(conn)
        version = 20
    if version < 21:
        _migrate_v21(conn)
        version = 21
    if version < 22:
        _migrate_v22(conn)
        version = 22
    if version < 23:
        _migrate_v23(conn)
        version = 23
    if version < 24:
        _migrate_v24(conn)
        version = 24
    if version < 25:
        _migrate_v25(conn)
        version = 25
    if version < 26:
        _migrate_v26(conn)
        version = 26
    if version < 27:
        _migrate_v27(conn)
        version = 27
    if version < 28:
        _migrate_v28(conn)
        version = 28
    if version < 29:
        _migrate_v29(conn)
        version = 29
    if version < 30:
        # Bring every supported pre-V30 shape to the canonical V29 state before
        # freezing its historical rows. These repairs are deliberately
        # idempotent and may normalize compatibility columns from older stores;
        # V30 itself must not mutate the resulting baseline.
        _repair_v29_device_lab_scene_table(conn)
        _repair_v29_espclaw_tables(conn)
        _repair_code_run_runtime_columns(conn)
        _repair_artifact_domain_status_consistency(conn)
        if source_version > 0:
            legacy_spec = _legacy_snapshot_spec(conn)
            legacy_digest, migrated_row_count = _legacy_snapshot_digest(
                conn, legacy_spec
            )
            legacy_context = (legacy_spec, legacy_digest, migrated_row_count)
        _migrate_v30(conn)
        version = 30
    if version < 31:
        _migrate_v31(conn)
        version = 31
    _repair_v30_creator_core_projections(conn)
    _repair_v30_creator_physical_runs(conn)
    _repair_v30_creator_deliveries(conn)
    _repair_v29_device_lab_scene_table(conn)
    _repair_v30_creator_idempotency(conn)
    _repair_v31_creator_code_variants(conn)
    _repair_v29_espclaw_tables(conn)
    _repair_code_run_runtime_columns(conn)
    _repair_artifact_domain_status_consistency(conn)
    _assert_foreign_keys_clean(conn)
    if legacy_context is not None:
        legacy_spec, legacy_digest, migrated_row_count = legacy_context
        post_digest, post_row_count = _legacy_snapshot_digest(
            conn, legacy_spec
        )
        if (
            post_digest != legacy_digest
            or post_row_count != migrated_row_count
        ):
            raise sqlite3.IntegrityError(
                "V29→V30 migration changed historical project rows."
            )
        _append_v30_migration_metrics(
            conn,
            legacy_digest=legacy_digest,
            migrated_row_count=migrated_row_count,
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migration_audit (
              id, from_version, to_version, status, backup_path, applied_at
            ) VALUES (?, 29, 30, 'applied', NULL, ?)
            """,
            ("migration_v29_v30", datetime.now(UTC).isoformat()),
        )
    conn.commit()


def _user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _repair_artifact_domain_status_consistency(conn: sqlite3.Connection) -> None:
    for table in ("artifacts", "artifact_versions"):
        conn.execute(
            f"""
            UPDATE {table}
            SET domain_status = CASE status
              WHEN 'NEEDS_REVIEW' THEN 'pending_confirmation'
              WHEN 'APPROVED' THEN 'confirmed'
              ELSE domain_status
            END
            WHERE (status = 'NEEDS_REVIEW' AND domain_status = 'draft')
               OR (status = 'APPROVED'
                   AND domain_status IN ('draft', 'pending_confirmation'))
            """
        )


def _create_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          stage TEXT NOT NULL,
          initial_idea TEXT NOT NULL DEFAULT '',
          selected_model TEXT NOT NULL,
          archived_at TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_opened_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE RESTRICT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          reasoning_content TEXT NULL,
          status TEXT NOT NULL,
          model TEXT NULL,
          error_json TEXT NULL,
          usage_json TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_project_created
          ON messages(project_id, created_at);

        CREATE TABLE IF NOT EXISTS drafts (
          project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
          content TEXT NOT NULL,
          updated_at TEXT NULL
        );

        PRAGMA user_version=1;
        """
    )


def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS solutions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          sections_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_solutions_project
          ON solutions(project_id, version);

        CREATE TABLE IF NOT EXISTS clarification_rounds (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          round_number INTEGER NOT NULL,
          completeness INTEGER NOT NULL,
          questions_json TEXT NOT NULL,
          answers_json TEXT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_clarification_project
          ON clarification_rounds(project_id, round_number);

        PRAGMA user_version=2;
        """
    )


def _migrate_v3(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS hardware_components (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          category TEXT NOT NULL,
          status TEXT NOT NULL,
          electrical_json TEXT NOT NULL,
          stock INTEGER NOT NULL DEFAULT 0,
          price REAL NOT NULL DEFAULT 0.0,
          age_recommendation INTEGER NULL,
          safety_tags_json TEXT NOT NULL DEFAULT '[]',
          notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_hardware_category
          ON hardware_components(category, status);

        PRAGMA user_version=3;
        """
    )


def _migrate_v4(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS proposals (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          solution_id TEXT NOT NULL REFERENCES solutions(id) ON DELETE RESTRICT,
          solution_version INTEGER NOT NULL,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          sections_json TEXT NOT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_proposals_project
          ON proposals(project_id, version);

        CREATE INDEX IF NOT EXISTS idx_proposals_solution
          ON proposals(solution_id, status);

        PRAGMA user_version=4;
        """
    )


def _migrate_v5(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS execution_plans (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          started_at TEXT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_execution_plans_project
          ON execution_plans(project_id, updated_at);

        CREATE TABLE IF NOT EXISTS task_nodes (
          id TEXT PRIMARY KEY,
          plan_id TEXT NOT NULL REFERENCES execution_plans(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          agent_id TEXT NOT NULL,
          title TEXT NOT NULL,
          description TEXT NOT NULL,
          status TEXT NOT NULL,
          dependencies_json TEXT NOT NULL,
          attempts INTEGER NOT NULL,
          max_attempts INTEGER NOT NULL,
          requires_approval INTEGER NOT NULL,
          logs_json TEXT NOT NULL,
          error TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          started_at TEXT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_task_nodes_plan
          ON task_nodes(plan_id, status);

        PRAGMA user_version=5;
        """
    )


def _migrate_v6(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_skills (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT NOT NULL,
          enabled INTEGER NOT NULL,
          input_schema_json TEXT NOT NULL,
          output_schema_json TEXT NOT NULL,
          permissions_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_user_skills_enabled
          ON user_skills(enabled, updated_at);

        CREATE TABLE IF NOT EXISTS model_route_audit (
          id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL,
          task_kind TEXT NOT NULL,
          strategy TEXT NOT NULL,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          fallback_model TEXT NULL,
          retry_count INTEGER NOT NULL,
          cost_tier TEXT NOT NULL,
          quality_tier TEXT NOT NULL,
          reasoning TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_model_route_audit_agent
          ON model_route_audit(agent_id, created_at);

        PRAGMA user_version=6;
        """
    )


def _migrate_v7(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artifacts (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          title TEXT NOT NULL,
          kind TEXT NOT NULL,
          status TEXT NOT NULL,
          source_agent_id TEXT NOT NULL,
          current_version_id TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_artifacts_project
          ON artifacts(project_id, status, updated_at);

        CREATE TABLE IF NOT EXISTS artifact_versions (
          id TEXT PRIMARY KEY,
          artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          preview_json TEXT NOT NULL,
          dependencies_json TEXT NOT NULL,
          producer_task_id TEXT NULL,
          source_entity_type TEXT NULL,
          source_entity_id TEXT NULL,
          checksum TEXT NOT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT NULL,
          UNIQUE(artifact_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_artifact_versions_artifact
          ON artifact_versions(artifact_id, version);

        CREATE INDEX IF NOT EXISTS idx_artifact_versions_source
          ON artifact_versions(source_entity_type, source_entity_id);

        CREATE TABLE IF NOT EXISTS floating_window_states (
          id TEXT PRIMARY KEY,
          project_id TEXT NULL REFERENCES projects(id) ON DELETE CASCADE,
          singleton_key TEXT NOT NULL,
          spec_json TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, singleton_key)
        );

        PRAGMA user_version=7;
        """
    )


def _migrate_v8(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS spec_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          validation_json TEXT NOT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_spec_runs_project
          ON spec_runs(project_id, version);

        CREATE TABLE IF NOT EXISTS spec_files (
          id TEXT PRIMARY KEY,
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_spec_files_run
          ON spec_files(spec_run_id, kind);

        PRAGMA user_version=8;
        """
    )


def _migrate_v9(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS code_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          workspace_root TEXT NOT NULL,
          max_retries INTEGER NOT NULL,
          retries INTEGER NOT NULL,
          test_result_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          accepted_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_code_runs_project
          ON code_runs(project_id, version);

        CREATE TABLE IF NOT EXISTS code_files (
          id TEXT PRIMARY KEY,
          code_run_id TEXT NOT NULL REFERENCES code_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          language TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_code_files_run
          ON code_files(code_run_id, path);

        CREATE TABLE IF NOT EXISTS code_patches (
          id TEXT PRIMARY KEY,
          code_run_id TEXT NOT NULL UNIQUE REFERENCES code_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          base_snapshot_id TEXT NULL,
          summary TEXT NOT NULL,
          diff TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        PRAGMA user_version=9;
        """
    )


def _migrate_v10(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS device_sessions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          port_id TEXT NOT NULL,
          board TEXT NOT NULL,
          status TEXT NOT NULL,
          logs_json TEXT NOT NULL,
          connected_at TEXT NULL,
          last_seen_at TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_device_sessions_project
          ON device_sessions(project_id, last_seen_at);

        CREATE TABLE IF NOT EXISTS device_operations (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          session_id TEXT NOT NULL REFERENCES device_sessions(id) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          status TEXT NOT NULL,
          dry_run INTEGER NOT NULL,
          command_label TEXT NOT NULL,
          log TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_device_operations_project
          ON device_operations(project_id, created_at);

        PRAGMA user_version=10;
        """
    )


def _migrate_v11(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cad_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id) ON DELETE RESTRICT,
          template_kind TEXT NOT NULL,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          command_label TEXT NOT NULL,
          parameters_json TEXT NOT NULL,
          validation_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cad_runs_project
          ON cad_runs(project_id, version);

        CREATE TABLE IF NOT EXISTS cad_files (
          id TEXT PRIMARY KEY,
          cad_run_id TEXT NOT NULL REFERENCES cad_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cad_files_run
          ON cad_files(cad_run_id, kind);

        PRAGMA user_version=11;
        """
    )


def _migrate_v12(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lesson_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id) ON DELETE RESTRICT,
          proposal_id TEXT NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          grade_band TEXT NOT NULL,
          lesson_hours INTEGER NOT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_lesson_runs_project
          ON lesson_runs(project_id, version);

        CREATE TABLE IF NOT EXISTS lesson_files (
          id TEXT PRIMARY KEY,
          lesson_run_id TEXT NOT NULL REFERENCES lesson_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_lesson_files_run
          ON lesson_files(lesson_run_id, kind);

        PRAGMA user_version=12;
        """
    )


def _migrate_v13(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS package_exports (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          status TEXT NOT NULL,
          title TEXT NOT NULL,
          file_name TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          privacy_report_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          zip_base64 TEXT NULL,
          created_at TEXT NOT NULL,
          imported_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_package_exports_project
          ON package_exports(project_id, created_at);

        PRAGMA user_version=13;
        """
    )


def _migrate_v14(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(messages)").fetchall()
    }
    if "structured_payload_json" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN structured_payload_json TEXT NULL")
    conn.execute("PRAGMA user_version=14")


def _migrate_v15(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(solutions)").fetchall()
    }
    if "based_on_version" not in columns:
        conn.execute("ALTER TABLE solutions ADD COLUMN based_on_version INTEGER NULL")
    if "change_summary_json" not in columns:
        conn.execute("ALTER TABLE solutions ADD COLUMN change_summary_json TEXT NULL")
    if "artifact_id" not in columns:
        conn.execute("ALTER TABLE solutions ADD COLUMN artifact_id TEXT NULL")
    if "artifact_version_id" not in columns:
        conn.execute("ALTER TABLE solutions ADD COLUMN artifact_version_id TEXT NULL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS solution_revisions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          base_solution_id TEXT NOT NULL REFERENCES solutions(id) ON DELETE RESTRICT,
          base_version INTEGER NOT NULL,
          new_solution_id TEXT NOT NULL REFERENCES solutions(id) ON DELETE RESTRICT,
          new_version INTEGER NOT NULL,
          user_request TEXT NOT NULL,
          changed_sections_json TEXT NOT NULL,
          preserved_sections_json TEXT NOT NULL,
          impact_summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_solution_revisions_project
          ON solution_revisions(project_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_solution_revisions_new_solution
          ON solution_revisions(new_solution_id);

        PRAGMA user_version=15;
        """
    )


def _migrate_v16(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(messages)").fetchall()
    }
    if "metadata_json" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT NULL")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversation_turns (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          client_turn_id TEXT NULL,
          parent_turn_id TEXT NULL,
          user_message_id TEXT NULL REFERENCES messages(id) ON DELETE SET NULL,
          assistant_message_id TEXT NULL REFERENCES messages(id) ON DELETE SET NULL,
          request_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, conversation_id, client_turn_id)
        );

        CREATE INDEX IF NOT EXISTS idx_conversation_turns_project
          ON conversation_turns(project_id, conversation_id, created_at);

        CREATE TABLE IF NOT EXISTS clarification_questions (
          id TEXT PRIMARY KEY,
          question_id TEXT NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          source_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
          stage TEXT NOT NULL,
          text TEXT NOT NULL,
          mode TEXT NOT NULL,
          options_json TEXT NOT NULL,
          required INTEGER NOT NULL,
          status TEXT NOT NULL,
          answered_at TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, conversation_id, source_message_id, question_id)
        );

        CREATE INDEX IF NOT EXISTS idx_clarification_questions_active
          ON clarification_questions(project_id, conversation_id, status, created_at);

        CREATE TABLE IF NOT EXISTS clarification_answers (
          id TEXT PRIMARY KEY,
          question_record_id TEXT NOT NULL REFERENCES clarification_questions(id) ON DELETE RESTRICT,
          question_id TEXT NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          answer_type TEXT NOT NULL,
          values_json TEXT NOT NULL,
          labels_json TEXT NOT NULL,
          user_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
          client_turn_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(question_record_id),
          UNIQUE(project_id, conversation_id, client_turn_id)
        );

        CREATE INDEX IF NOT EXISTS idx_clarification_answers_project
          ON clarification_answers(project_id, conversation_id, created_at);

        PRAGMA user_version=16;
        """
    )


def _migrate_v17(conn: sqlite3.Connection) -> None:
    _remove_conversation_project_unique(conn)
    _add_column(conn, "projects", "active_expert_id", "TEXT NULL")
    _add_column(conn, "artifacts", "owner_expert_id", "TEXT NULL")
    _add_column(conn, "artifacts", "owner_expert_type", "TEXT NULL")
    _add_column(conn, "artifacts", "source_conversation_id", "TEXT NULL")
    _add_column(conn, "artifacts", "shared_context_revision", "INTEGER NULL")
    _add_column(conn, "artifact_versions", "shared_context_revision", "INTEGER NULL")
    _add_column(conn, "code_runs", "hardware_solution_version", "INTEGER NULL")
    _add_column(conn, "code_runs", "bom_version", "INTEGER NULL")
    _add_column(conn, "code_runs", "io_map_version", "INTEGER NULL")
    _add_column(conn, "code_runs", "generated_by_expert_id", "TEXT NULL")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS expert_definitions (
          id TEXT PRIMARY KEY,
          expert_type TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          description TEXT NOT NULL,
          icon TEXT NOT NULL,
          built_in INTEGER NOT NULL,
          skill_ids_json TEXT NOT NULL,
          supported_artifact_types_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS project_shared_contexts (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
          revision INTEGER NOT NULL,
          goals_json TEXT NOT NULL,
          constraints_json TEXT NOT NULL,
          requirements_json TEXT NOT NULL,
          decisions_json TEXT NOT NULL,
          active_artifact_versions_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shared_context_changes (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          source_expert_id TEXT NOT NULL,
          change_type TEXT NOT NULL,
          field TEXT NOT NULL,
          previous_value_json TEXT NULL,
          next_value_json TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS project_experts (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          expert_definition_id TEXT NOT NULL REFERENCES expert_definitions(id) ON DELETE RESTRICT,
          expert_type TEXT NOT NULL,
          conversation_id TEXT NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE RESTRICT,
          private_memory_id TEXT NOT NULL,
          status TEXT NOT NULL,
          current_task TEXT NULL,
          added_at TEXT NOT NULL,
          removed_at TEXT NULL,
          UNIQUE(project_id, expert_type)
        );

        CREATE INDEX IF NOT EXISTS idx_project_experts_project
          ON project_experts(project_id, removed_at, expert_type);

        CREATE TABLE IF NOT EXISTS expert_private_memories (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          project_expert_id TEXT NOT NULL UNIQUE REFERENCES project_experts(id) ON DELETE CASCADE,
          notes_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS expert_drafts (
          project_expert_id TEXT PRIMARY KEY REFERENCES project_experts(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          content TEXT NOT NULL,
          updated_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS project_coordinator_states (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
          current_item_json TEXT NULL,
          conflicts_json TEXT NOT NULL,
          dependencies_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    _seed_expert_definitions(conn)
    _backfill_project_workspaces(conn)
    conn.execute("PRAGMA user_version=17")


def _migrate_v18(conn: sqlite3.Connection) -> None:
    _seed_expert_definitions(conn)
    conn.execute("PRAGMA user_version=18")


def _migrate_v19(conn: sqlite3.Connection) -> None:
    _rebuild_project_experts_v19(conn)
    _add_column(conn, "conversations", "owner_expert_type", "TEXT NULL")
    _add_column(conn, "conversations", "legacy_expert_type", "TEXT NULL")
    _add_column(
        conn,
        "conversations",
        "archived_legacy_thread",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(conn, "artifacts", "legacy_owner_expert", "TEXT NULL")
    _add_column(conn, "artifacts", "creator_legacy_expert", "TEXT NULL")
    _add_column(conn, "artifacts", "domain_status", "TEXT NULL")
    _add_column(conn, "artifact_versions", "domain_status", "TEXT NULL")
    _create_three_expert_domain_tables(conn)
    _seed_expert_definitions(conn)
    _normalize_expert_rows_v19(conn)
    _ensure_canonical_project_workspaces_v19(conn)
    _normalize_artifact_owners_v19(conn)
    _normalize_shared_context_v19(conn)
    _backfill_artifact_dependency_index_v19(conn)
    conn.execute("PRAGMA user_version=19")


def _migrate_v20(conn: sqlite3.Connection) -> None:
    _add_column(conn, "project_shared_facts", "key", "TEXT NULL")
    conn.execute(
        """
        UPDATE project_shared_facts
        SET key = field
        WHERE key IS NULL OR key = ''
        """
    )
    _add_column(
        conn,
        "project_pending_items",
        "critical_path",
        "INTEGER NOT NULL DEFAULT 0",
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_tasks (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL,
          owner_expert_type TEXT NOT NULL,
          status TEXT NOT NULL,
          dependency_task_ids_json TEXT NOT NULL,
          artifact_ids_json TEXT NOT NULL,
          current_pending_item_id TEXT NULL REFERENCES project_pending_items(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_tasks_project
          ON project_tasks(project_id, status, updated_at);

        CREATE INDEX IF NOT EXISTS idx_project_shared_facts_key
          ON project_shared_facts(project_id, key, status, updated_at);

        CREATE INDEX IF NOT EXISTS idx_artifact_dependencies_upstream_version
          ON artifact_dependencies(project_id, upstream_artifact_id, upstream_version);
        """
    )
    conn.execute("PRAGMA user_version=20")


def _migrate_v21(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS expert_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          project_expert_id TEXT NOT NULL REFERENCES project_experts(id) ON DELETE CASCADE,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          expert_type TEXT NOT NULL,
          request_message_id TEXT NULL REFERENCES messages(id) ON DELETE SET NULL,
          response_message_id TEXT NULL REFERENCES messages(id) ON DELETE SET NULL,
          status TEXT NOT NULL,
          retry_count INTEGER NOT NULL DEFAULT 0,
          context_json TEXT NOT NULL,
          output_json TEXT NULL,
          error TEXT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_expert_runs_project
          ON expert_runs(project_id, created_at);

        CREATE TABLE IF NOT EXISTS skill_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          expert_run_id TEXT NULL REFERENCES expert_runs(id) ON DELETE SET NULL,
          skill_id TEXT NOT NULL,
          owner_expert_type TEXT NULL,
          status TEXT NOT NULL,
          input_json TEXT NOT NULL,
          output_json TEXT NULL,
          error TEXT NULL,
          retry_count INTEGER NOT NULL DEFAULT 0,
          confirmation_required INTEGER NOT NULL DEFAULT 0,
          confirmed_at TEXT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_skill_runs_project
          ON skill_runs(project_id, created_at);

        CREATE TABLE IF NOT EXISTS tool_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          skill_run_id TEXT NOT NULL REFERENCES skill_runs(id) ON DELETE CASCADE,
          tool_id TEXT NOT NULL,
          status TEXT NOT NULL,
          input_json TEXT NOT NULL,
          output_json TEXT NULL,
          error TEXT NULL,
          retry_count INTEGER NOT NULL DEFAULT 0,
          timeout_ms INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tool_runs_skill
          ON tool_runs(skill_run_id, created_at);

        CREATE TABLE IF NOT EXISTS schema_migration_audit (
          id TEXT PRIMARY KEY,
          from_version INTEGER NOT NULL,
          to_version INTEGER NOT NULL,
          status TEXT NOT NULL,
          backup_path TEXT NULL,
          applied_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 20, 21, 'applied', NULL, ?)
        """,
        ("migration_v20_v21", now),
    )
    conn.execute("PRAGMA user_version=21")


def _migrate_v22(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE clarification_answers_v22 (
          id TEXT PRIMARY KEY,
          question_record_id TEXT NOT NULL REFERENCES clarification_questions(id) ON DELETE RESTRICT,
          question_id TEXT NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          answer_type TEXT NOT NULL,
          values_json TEXT NOT NULL,
          labels_json TEXT NOT NULL,
          user_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
          client_turn_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(question_record_id)
        );

        INSERT INTO clarification_answers_v22 (
          id, question_record_id, question_id, project_id, conversation_id,
          answer_type, values_json, labels_json, user_message_id,
          client_turn_id, created_at
        )
        SELECT
          id, question_record_id, question_id, project_id, conversation_id,
          answer_type, values_json, labels_json, user_message_id,
          client_turn_id, created_at
        FROM clarification_answers;

        DROP TABLE clarification_answers;
        ALTER TABLE clarification_answers_v22 RENAME TO clarification_answers;

        CREATE INDEX idx_clarification_answers_project
          ON clarification_answers(project_id, conversation_id, created_at);

        CREATE INDEX idx_clarification_answers_turn
          ON clarification_answers(project_id, conversation_id, client_turn_id);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 21, 22, 'applied', NULL, ?)
        """,
        ("migration_v21_v22", now),
    )
    conn.execute("PRAGMA user_version=22")


def _migrate_v23(conn: sqlite3.Connection) -> None:
    """Allow conversational CodeRuns without manufacturing a Spec dependency."""

    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE code_runs_v23 (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          spec_run_id TEXT NULL REFERENCES spec_runs(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          workspace_root TEXT NOT NULL,
          max_retries INTEGER NOT NULL,
          retries INTEGER NOT NULL,
          test_result_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          hardware_solution_version INTEGER NULL,
          bom_version INTEGER NULL,
          io_map_version INTEGER NULL,
          generated_by_expert_id TEXT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          accepted_at TEXT NULL
        );

        CREATE TABLE code_files_v23 (
          id TEXT PRIMARY KEY,
          code_run_id TEXT NOT NULL REFERENCES code_runs_v23(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          language TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE code_patches_v23 (
          id TEXT PRIMARY KEY,
          code_run_id TEXT NOT NULL UNIQUE REFERENCES code_runs_v23(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          base_snapshot_id TEXT NULL,
          summary TEXT NOT NULL,
          diff TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        INSERT INTO code_runs_v23 (
          id, project_id, spec_run_id, version, status, workspace_root,
          max_retries, retries, test_result_json, artifact_id,
          artifact_version_id, hardware_solution_version, bom_version,
          io_map_version, generated_by_expert_id, stale_reason,
          created_at, updated_at, accepted_at
        )
        SELECT
          id, project_id, spec_run_id, version, status, workspace_root,
          max_retries, retries, test_result_json, artifact_id,
          artifact_version_id, hardware_solution_version, bom_version,
          io_map_version, generated_by_expert_id, stale_reason,
          created_at, updated_at, accepted_at
        FROM code_runs;

        INSERT INTO code_files_v23 (
          id, code_run_id, project_id, kind, path, language, content, created_at
        )
        SELECT id, code_run_id, project_id, kind, path, language, content, created_at
        FROM code_files;

        INSERT INTO code_patches_v23 (
          id, code_run_id, project_id, base_snapshot_id, summary, diff, created_at
        )
        SELECT id, code_run_id, project_id, base_snapshot_id, summary, diff, created_at
        FROM code_patches;

        DROP TABLE code_files;
        DROP TABLE code_patches;
        DROP TABLE code_runs;

        ALTER TABLE code_runs_v23 RENAME TO code_runs;
        ALTER TABLE code_files_v23 RENAME TO code_files;
        ALTER TABLE code_patches_v23 RENAME TO code_patches;

        CREATE INDEX idx_code_runs_project
          ON code_runs(project_id, version);
        CREATE INDEX idx_code_files_run
          ON code_files(code_run_id, path);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 22, 23, 'applied', NULL, ?)
        """,
        ("migration_v22_v23", now),
    )
    conn.execute("PRAGMA user_version=23")


def _migrate_v24(conn: sqlite3.Connection) -> None:
    """Add persistent CAD jobs and binary artifact metadata.

    The v11 CAD tables stored generated text directly in ``cad_files`` and
    required a Spec row.  v24 keeps those rows readable while rebuilding the
    tables with nullable Spec references and immutable engine/source metadata.
    No legacy content is discarded during the copy.
    """

    now = datetime.now(UTC).isoformat()
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _execute_sql_script(
            conn,
            """
            CREATE TABLE IF NOT EXISTS cad_jobs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
              cad_run_id TEXT NOT NULL REFERENCES cad_runs(id) ON DELETE CASCADE,
              client_request_id TEXT NULL,
              status TEXT NOT NULL,
              phase TEXT NOT NULL,
              progress INTEGER NOT NULL DEFAULT 0
                CHECK(progress >= 0 AND progress <= 100),
              source_message_id TEXT NULL REFERENCES messages(id) ON DELETE SET NULL,
              project_expert_id TEXT NULL REFERENCES project_experts(id) ON DELETE SET NULL,
              spec_run_id TEXT NULL REFERENCES spec_runs(id) ON DELETE SET NULL,
              request_hash TEXT NOT NULL,
              request_json TEXT NOT NULL,
              result_json TEXT NULL,
              error_json TEXT NULL,
              created_at TEXT NOT NULL,
              started_at TEXT NULL,
              completed_at TEXT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cad_jobs_project_status
              ON cad_jobs(project_id, status, created_at);
            CREATE INDEX IF NOT EXISTS idx_cad_jobs_run
              ON cad_jobs(cad_run_id, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cad_jobs_client_request
              ON cad_jobs(project_id, client_request_id)
              WHERE client_request_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS artifact_files (
              id TEXT PRIMARY KEY,
              artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
              artifact_version_id TEXT NOT NULL
                REFERENCES artifact_versions(id) ON DELETE CASCADE,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
              role TEXT NOT NULL,
              file_name TEXT NOT NULL,
              storage_key TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
              sha256 TEXT NOT NULL,
              triangle_count INTEGER NULL
                CHECK(triangle_count IS NULL OR triangle_count >= 0),
              bounds_json TEXT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(artifact_version_id, role, file_name),
              UNIQUE(storage_key)
            );

            CREATE INDEX IF NOT EXISTS idx_artifact_files_version
              ON artifact_files(artifact_version_id, role);
            CREATE INDEX IF NOT EXISTS idx_artifact_files_project
              ON artifact_files(project_id, created_at);

            CREATE TABLE IF NOT EXISTS mechanical_profile_versions (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL,
              revision TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              display_name TEXT NOT NULL,
              source TEXT NOT NULL,
              evidence_level TEXT NOT NULL,
              representation TEXT NOT NULL,
              profile_json TEXT NOT NULL,
              content_sha256 TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(profile_id, revision)
            );

            CREATE INDEX IF NOT EXISTS idx_mechanical_profiles_identity
              ON mechanical_profile_versions(profile_id, revision);

            CREATE TABLE IF NOT EXISTS hardware_mechanical_links (
              id TEXT PRIMARY KEY,
              hardware_component_id TEXT NOT NULL
                REFERENCES hardware_components(id) ON DELETE CASCADE,
              mechanical_profile_id TEXT NOT NULL,
              mechanical_profile_revision TEXT NOT NULL,
              evidence_level TEXT NOT NULL,
              confirmed_at TEXT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(hardware_component_id, mechanical_profile_id),
              FOREIGN KEY(mechanical_profile_id, mechanical_profile_revision)
                REFERENCES mechanical_profile_versions(profile_id, revision)
                ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_hardware_mechanical_links_profile
              ON hardware_mechanical_links(mechanical_profile_id,
                                            mechanical_profile_revision);
            """
        )

        # Snapshot legacy rows before replacing their table definitions.
        legacy_runs: list[tuple[object, ...]] = []
        legacy_files: list[tuple[object, ...]] = []
        has_runs = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cad_runs'"
        ).fetchone()
        if has_runs:
            legacy_runs = conn.execute(
                """
                SELECT id, project_id, spec_run_id, template_kind, version, status,
                       command_label, parameters_json, validation_json, artifact_id,
                       artifact_version_id, stale_reason, created_at, updated_at,
                       confirmed_at
                FROM cad_runs
                """
            ).fetchall()
        has_files = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cad_files'"
        ).fetchone()
        if has_files:
            legacy_files = conn.execute(
                """
                SELECT id, cad_run_id, project_id, kind, path, mime_type, content,
                       artifact_id, artifact_version_id, created_at
                FROM cad_files
                """
            ).fetchall()

        _execute_sql_script(
            conn,
            """
            DROP TABLE IF EXISTS cad_files_v24;
            DROP TABLE IF EXISTS cad_runs_v24;

            CREATE TABLE cad_runs_v24 (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
              spec_run_id TEXT NULL REFERENCES spec_runs(id) ON DELETE RESTRICT,
              template_kind TEXT NOT NULL,
              version INTEGER NOT NULL,
              status TEXT NOT NULL,
              command_label TEXT NOT NULL,
              parameters_json TEXT NOT NULL,
              validation_json TEXT NOT NULL,
              artifact_id TEXT NULL,
              artifact_version_id TEXT NULL,
              source_message_id TEXT NULL REFERENCES messages(id) ON DELETE SET NULL,
              generated_by_expert_id TEXT NULL REFERENCES project_experts(id)
                ON DELETE SET NULL,
              engine_id TEXT NOT NULL DEFAULT 'template-dry-run',
              engine_version TEXT NULL,
              design_state_json TEXT NULL,
              latest_job_id TEXT NULL REFERENCES cad_jobs(id) ON DELETE SET NULL,
              stale_reason TEXT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              confirmed_at TEXT NULL
            );

            CREATE TABLE cad_files_v24 (
              id TEXT PRIMARY KEY,
              cad_run_id TEXT NOT NULL REFERENCES cad_runs_v24(id) ON DELETE CASCADE,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
              kind TEXT NULL,
              role TEXT NULL,
              path TEXT NOT NULL DEFAULT '',
              file_name TEXT NOT NULL DEFAULT '',
              storage_key TEXT NULL,
              mime_type TEXT NOT NULL,
              content TEXT NULL,
              byte_size INTEGER NOT NULL DEFAULT 0 CHECK(byte_size >= 0),
              sha256 TEXT NULL,
              bounds_json TEXT NULL,
              triangle_count INTEGER NULL CHECK(triangle_count IS NULL OR triangle_count >= 0),
              artifact_file_id TEXT NULL REFERENCES artifact_files(id) ON DELETE SET NULL,
              artifact_id TEXT NULL,
              artifact_version_id TEXT NULL,
              created_at TEXT NOT NULL
            );
            """
        )

        conn.executemany(
            """
            INSERT INTO cad_runs_v24 (
              id, project_id, spec_run_id, template_kind, version, status,
              command_label, parameters_json, validation_json, artifact_id,
              artifact_version_id, source_message_id, generated_by_expert_id,
              engine_id, engine_version, design_state_json, latest_job_id,
              stale_reason, created_at, updated_at, confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL,
                      'template-dry-run', '1', '{}', NULL, ?, ?, ?, ?)
            """,
            [
                (
                    *row[:11],
                    row[11],
                    row[12],
                    row[13],
                    row[14],
                )
                for row in legacy_runs
            ],
        )

        role_by_kind = {
            "STEP": "STEP_ASSEMBLY",
            "STL": "STL_PRINTABLE_PARTS",
            "PARAMETERS": "PARAMETERS",
        }
        file_rows: list[tuple[object, ...]] = []
        for row in legacy_files:
            content = row[6]
            content_text = str(content) if content is not None else None
            path = str(row[4]) if row[4] is not None else ""
            file_name = path.replace("\\", "/").rsplit("/", 1)[-1] or str(row[0])
            digest = (
                hashlib.sha256(content_text.encode("utf-8")).hexdigest()
                if content_text is not None
                else None
            )
            file_rows.append(
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    role_by_kind.get(str(row[3]), str(row[3])),
                    row[4],
                    file_name,
                    None,
                    row[5],
                    content_text,
                    len(content_text.encode("utf-8")) if content_text is not None else 0,
                    digest,
                    None,
                    None,
                    None,
                    row[7],
                    row[8],
                    row[9],
                )
            )
        conn.executemany(
            """
            INSERT INTO cad_files_v24 (
              id, cad_run_id, project_id, kind, role, path, file_name,
              storage_key, mime_type, content, byte_size, sha256, bounds_json,
              triangle_count, artifact_file_id, artifact_id, artifact_version_id,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            file_rows,
        )

        if has_files:
            conn.execute("DROP TABLE cad_files")
        if has_runs:
            conn.execute("DROP TABLE cad_runs")
        conn.execute("ALTER TABLE cad_runs_v24 RENAME TO cad_runs")
        conn.execute("ALTER TABLE cad_files_v24 RENAME TO cad_files")
        _execute_sql_script(
            conn,
            """
            CREATE INDEX IF NOT EXISTS idx_cad_runs_project
              ON cad_runs(project_id, version);
            CREATE INDEX IF NOT EXISTS idx_cad_runs_latest_job
              ON cad_runs(latest_job_id);
            CREATE INDEX IF NOT EXISTS idx_cad_files_run
              ON cad_files(cad_run_id, role, kind);
            """
        )
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migration_audit'"
        ).fetchone():
            conn.execute(
                """
                INSERT OR IGNORE INTO schema_migration_audit (
                  id, from_version, to_version, status, backup_path, applied_at
                ) VALUES (?, 23, 24, 'applied', NULL, ?)
                """,
                ("migration_v23_v24", now),
            )
        conn.execute("PRAGMA user_version=24")
        _assert_foreign_keys_clean(conn)
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _migrate_v25(conn: sqlite3.Connection) -> None:
    """Link local execution confirmations to exactly one resumable SkillRun."""

    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS skill_run_authorizations (
          pending_item_id TEXT PRIMARY KEY
            REFERENCES project_pending_items(id) ON DELETE RESTRICT,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          skill_run_id TEXT NOT NULL UNIQUE REFERENCES skill_runs(id) ON DELETE RESTRICT,
          created_at TEXT NOT NULL,
          claimed_at TEXT NULL,
          completed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_skill_run_authorizations_project
          ON skill_run_authorizations(project_id, created_at);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 24, 25, 'applied', NULL, ?)
        """,
        ("migration_v24_v25", now),
    )
    conn.execute("PRAGMA user_version=25")


def _migrate_v26(conn: sqlite3.Connection) -> None:
    """Bind projects and current workspace state to an authenticated subject."""

    now = datetime.now(UTC).isoformat()
    if "owner_subject" not in _table_columns(conn, "projects"):
        conn.execute("ALTER TABLE projects ADD COLUMN owner_subject TEXT NULL")
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_projects_owner_activity
          ON projects(owner_subject, archived_at, last_opened_at, updated_at);

        CREATE TABLE IF NOT EXISTS account_workspace_state (
          owner_subject TEXT PRIMARY KEY,
          current_project_id TEXT NULL REFERENCES projects(id) ON DELETE SET NULL,
          legacy_claim_decision_at TEXT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    stale_pending_ids = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT id FROM project_pending_items
            WHERE status = 'open' AND title = '从初始专家开始'
            """
        ).fetchall()
    ]
    if stale_pending_ids:
        placeholders = ",".join("?" for _ in stale_pending_ids)
        conn.execute(
            f"""
            UPDATE project_pending_items
            SET status = 'dismissed', is_highlighted = 0, updated_at = ?
            WHERE id IN ({placeholders})
            """,
            (now, *stale_pending_ids),
        )
        conn.execute(
            f"""
            UPDATE project_tasks
            SET current_pending_item_id = NULL, updated_at = ?
            WHERE current_pending_item_id IN ({placeholders})
            """,
            (now, *stale_pending_ids),
        )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 25, 26, 'applied', NULL, ?)
        """,
        ("migration_v25_v26", now),
    )
    conn.execute("PRAGMA user_version=26")


def _migrate_v27(conn: sqlite3.Connection) -> None:
    """Add the V2 Project Kernel, capability facade and local job envelope."""

    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_state_snapshots (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          project_version INTEGER NOT NULL,
          schema_version INTEGER NOT NULL,
          projection_json TEXT NOT NULL,
          projection_hash TEXT NOT NULL,
          projected_at TEXT NOT NULL,
          UNIQUE(project_id, project_version)
        );

        CREATE INDEX IF NOT EXISTS idx_project_state_snapshots_project
          ON project_state_snapshots(project_id, project_version DESC);

        CREATE TABLE IF NOT EXISTS project_events (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          sequence INTEGER NOT NULL,
          event_type TEXT NOT NULL,
          change_set_id TEXT NULL,
          project_version INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(project_id, sequence)
        );

        CREATE INDEX IF NOT EXISTS idx_project_events_project
          ON project_events(project_id, sequence);

        CREATE TABLE IF NOT EXISTS project_change_sets (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          base_project_version INTEGER NOT NULL,
          author_type TEXT NOT NULL,
          owner_domain TEXT NOT NULL,
          intent_summary TEXT NOT NULL,
          operations_json TEXT NOT NULL,
          affected_facts_json TEXT NOT NULL,
          affected_artifacts_json TEXT NOT NULL,
          capability_bindings_json TEXT NOT NULL,
          validation_results_json TEXT NOT NULL,
          risk_level TEXT NOT NULL,
          confirmation_policy TEXT NOT NULL,
          status TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          committed_at TEXT NULL,
          UNIQUE(project_id, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_project_change_sets_project
          ON project_change_sets(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS project_versions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          version INTEGER NOT NULL,
          state_hash TEXT NOT NULL,
          change_set_id TEXT NULL REFERENCES project_change_sets(id) ON DELETE RESTRICT,
          capability_snapshot_hash TEXT NOT NULL,
          artifact_version_ids_json TEXT NOT NULL,
          validation_summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(project_id, version)
        );

        CREATE TABLE IF NOT EXISTS project_releases (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          project_version_id TEXT NOT NULL REFERENCES project_versions(id) ON DELETE RESTRICT,
          name TEXT NOT NULL,
          manifest_hash TEXT NOT NULL,
          artifact_version_ids_json TEXT NOT NULL,
          unverified_items_json TEXT NOT NULL,
          notes TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_releases_project
          ON project_releases(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS capabilities (
          id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          status TEXT NOT NULL,
          name TEXT NOT NULL,
          version TEXT NOT NULL,
          source_type TEXT NOT NULL,
          source_id TEXT NOT NULL,
          revision TEXT NOT NULL,
          host_requirements_json TEXT NOT NULL,
          risk_level TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(source_type, source_id, revision)
        );

        CREATE TABLE IF NOT EXISTS capability_relations (
          id TEXT PRIMARY KEY,
          from_capability_id TEXT NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
          to_capability_id TEXT NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
          relation TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          UNIQUE(from_capability_id, to_capability_id, relation)
        );

        CREATE TABLE IF NOT EXISTS project_capability_bindings (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          capability_id TEXT NOT NULL REFERENCES capabilities(id) ON DELETE RESTRICT,
          requirement_key TEXT NOT NULL,
          bound_at TEXT NOT NULL,
          unbound_at TEXT NULL,
          UNIQUE(project_id, capability_id, requirement_key)
        );

        CREATE INDEX IF NOT EXISTS idx_project_capability_bindings_project
          ON project_capability_bindings(project_id, unbound_at);

        CREATE TABLE IF NOT EXISTS tool_jobs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          status TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          request_json TEXT NOT NULL,
          host_lease_id TEXT NULL,
          progress INTEGER NOT NULL DEFAULT 0,
          result_artifact_ids_json TEXT NOT NULL,
          error_json TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, kind, request_hash)
        );

        CREATE INDEX IF NOT EXISTS idx_tool_jobs_project
          ON tool_jobs(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS local_bridge_sessions (
          id TEXT PRIMARY KEY,
          owner_subject TEXT NULL,
          origin TEXT NOT NULL,
          project_id TEXT NULL REFERENCES projects(id) ON DELETE CASCADE,
          challenge_hash TEXT NOT NULL,
          capabilities_json TEXT NOT NULL,
          issued_at TEXT NULL,
          expires_at TEXT NULL,
          revoked_at TEXT NULL,
          last_seen_at TEXT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_local_bridge_sessions_origin
          ON local_bridge_sessions(origin, revoked_at, expires_at);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 26, 27, 'applied', NULL, ?)
        """,
        ("migration_v26_v27", now),
    )
    conn.execute("PRAGMA user_version=27")


def _migrate_v28(conn: sqlite3.Connection) -> None:
    """Persist CAD Intent source revisions without adopting its legacy project store."""

    now = datetime.now(UTC).isoformat()
    if "result_json" not in _table_columns(conn, "tool_jobs"):
        conn.execute("ALTER TABLE tool_jobs ADD COLUMN result_json TEXT NULL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cad_intent_revisions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          parent_revision_id TEXT NULL REFERENCES cad_intent_revisions(id) ON DELETE RESTRICT,
          tool_job_id TEXT NOT NULL REFERENCES tool_jobs(id) ON DELETE RESTRICT,
          change_set_id TEXT NULL REFERENCES project_change_sets(id) ON DELETE RESTRICT,
          project_version_id TEXT NULL REFERENCES project_versions(id) ON DELETE RESTRICT,
          intent_summary TEXT NOT NULL,
          route_action TEXT NOT NULL,
          status TEXT NOT NULL,
          source_storage_key TEXT NULL,
          base_source_sha256 TEXT NULL,
          source_sha256 TEXT NULL,
          pending_patch_json TEXT NULL,
          object_index_json TEXT NOT NULL,
          artifact_id TEXT NULL REFERENCES artifacts(id) ON DELETE RESTRICT,
          artifact_version_id TEXT NULL REFERENCES artifact_versions(id) ON DELETE RESTRICT,
          created_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cad_intent_revisions_project
          ON cad_intent_revisions(project_id, created_at DESC);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 27, 28, 'applied', NULL, ?)
        """,
        ("migration_v27_v28", now),
    )
    conn.execute("PRAGMA user_version=28")


def _migrate_v29(conn: sqlite3.Connection) -> None:
    """Add the two-board device lab, application imports and immutable parameters."""

    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS firmware_applications (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          application_id TEXT NOT NULL,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('seeedstudio/xiao_esp32s3_sense', 'dfrobot/dfrobot_k10')
          ),
          manifest_json TEXT NOT NULL,
          archive_path TEXT NOT NULL,
          archive_sha256 TEXT NOT NULL,
          simulation_capability TEXT NOT NULL CHECK (
            simulation_capability IN ('FULL', 'UART_ONLY', 'NONE')
          ),
          imported_at TEXT NOT NULL,
          UNIQUE(project_id, application_id, archive_sha256)
        );

        CREATE INDEX IF NOT EXISTS idx_firmware_applications_project
          ON firmware_applications(project_id, imported_at DESC);

        CREATE TABLE IF NOT EXISTS device_parameter_sets (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('seeedstudio/xiao_esp32s3_sense', 'dfrobot/dfrobot_k10')
          ),
          profile_revision TEXT NOT NULL,
          revision INTEGER NOT NULL,
          label TEXT NOT NULL,
          values_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(project_id, board_id, revision)
        );

        CREATE INDEX IF NOT EXISTS idx_device_parameter_sets_project
          ON device_parameter_sets(project_id, board_id, revision DESC);

        CREATE TABLE IF NOT EXISTS device_lab_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('seeedstudio/xiao_esp32s3_sense', 'dfrobot/dfrobot_k10')
          ),
          target TEXT NOT NULL CHECK (target IN ('SIMULATOR', 'DEVICE')),
          engine TEXT NOT NULL CHECK (engine IN ('FUNCTIONAL_MODEL', 'QEMU_ESP32S3')),
          status TEXT NOT NULL CHECK (status IN ('STARTING', 'RUNNING', 'STOPPED', 'ERROR')),
          application_id TEXT NULL REFERENCES firmware_applications(id) ON DELETE SET NULL,
          parameter_set_id TEXT NULL REFERENCES device_parameter_sets(id) ON DELETE SET NULL,
          state_json TEXT NOT NULL,
          started_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          stopped_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_device_lab_runs_project
          ON device_lab_runs(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS device_lab_events (
          run_id TEXT NOT NULL REFERENCES device_lab_runs(id) ON DELETE CASCADE,
          revision INTEGER NOT NULL,
          event_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(run_id, revision)
        );

        CREATE TABLE IF NOT EXISTS device_lab_scenes (
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision TEXT NOT NULL,
          proposal_id TEXT NOT NULL,
          proposal_version INTEGER NOT NULL,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('seeedstudio/xiao_esp32s3_sense', 'dfrobot/dfrobot_k10')
          ),
          scene_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(project_id, revision)
        );

        CREATE INDEX IF NOT EXISTS idx_device_lab_scenes_project
          ON device_lab_scenes(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS espclaw_endpoints (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          session_id TEXT NOT NULL UNIQUE REFERENCES device_sessions(id) ON DELETE CASCADE,
          web_endpoint TEXT NOT NULL,
          mcp_endpoint TEXT NOT NULL,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('dfrobot/dfrobot_k10', 'seeedstudio/xiao_esp32s3_sense')
          ),
          status TEXT NOT NULL CHECK (status IN ('READY', 'ERROR')),
          storage_base_path TEXT NOT NULL CHECK (storage_base_path = '/fatfs'),
          capabilities_json TEXT NOT NULL,
          paired_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, web_endpoint)
        );

        CREATE INDEX IF NOT EXISTS idx_espclaw_endpoints_project
          ON espclaw_endpoints(project_id, last_seen_at DESC);

        CREATE TABLE IF NOT EXISTS espclaw_deployments (
          operation_id TEXT PRIMARY KEY REFERENCES device_operations(id) ON DELETE CASCADE,
          endpoint_id TEXT NOT NULL REFERENCES espclaw_endpoints(id) ON DELETE CASCADE,
          code_run_id TEXT NOT NULL,
          version_path TEXT NOT NULL,
          entrypoint_path TEXT NOT NULL,
          fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_espclaw_deployments_endpoint
          ON espclaw_deployments(endpoint_id, created_at DESC);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES (?, 28, 29, 'applied', NULL, ?)
        """,
        ("migration_v28_v29", now),
    )
    conn.execute("PRAGMA user_version=29")


def _migrate_v30(conn: sqlite3.Connection) -> None:
    """Add Creator V3 revisions, evidence, commands and metric events."""

    now = datetime.now(UTC).isoformat()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creator_work_state (
          project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
          creator_version INTEGER NOT NULL DEFAULT 0 CHECK (creator_version >= 0),
          origin TEXT NOT NULL DEFAULT 'LEGACY' CHECK (origin IN ('CREATOR', 'LEGACY')),
          last_stage TEXT NOT NULL DEFAULT 'IDEA_SOLUTION' CHECK (
            last_stage IN ('IDEA_SOLUTION', 'DIGITAL_PROTOTYPE', 'STRUCTURE_3D', 'PHYSICAL_RUN')
          ),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS creator_goal_revisions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision INTEGER NOT NULL CHECK (revision > 0),
          status TEXT NOT NULL CHECK (status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')),
          statement TEXT NOT NULL,
          observable_behavior TEXT NOT NULL,
          constraints_json TEXT NOT NULL,
          success_criteria_json TEXT NOT NULL,
          source_message_id TEXT NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT NULL,
          UNIQUE(project_id, revision)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_goals_project
          ON creator_goal_revisions(project_id, revision DESC);

        CREATE TABLE IF NOT EXISTS creator_solution_revisions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision INTEGER NOT NULL CHECK (revision > 0),
          status TEXT NOT NULL CHECK (status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')),
          summary TEXT NOT NULL,
          logic TEXT NOT NULL,
          hardware TEXT NOT NULL,
          software TEXT NOT NULL,
          structure TEXT NOT NULL,
          simulation TEXT NOT NULL,
          safety TEXT NOT NULL,
          bom_json TEXT NOT NULL,
          io_map_json TEXT NOT NULL,
          source_proposal_id TEXT NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT NULL,
          UNIQUE(project_id, revision)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_solutions_project
          ON creator_solution_revisions(project_id, revision DESC);

        CREATE TABLE IF NOT EXISTS creator_acceptance_scenarios (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          solution_revision_id TEXT NULL REFERENCES creator_solution_revisions(id) ON DELETE SET NULL,
          title TEXT NOT NULL,
          required INTEGER NOT NULL CHECK (required IN (0, 1)),
          simulation_expected TEXT NOT NULL,
          physical_expected TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_scenarios_project
          ON creator_acceptance_scenarios(project_id, created_at ASC);

        CREATE TABLE IF NOT EXISTS creator_evidence (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK (kind IN (
            'GOAL_CONFIRMATION', 'STATIC_VALIDATION', 'SIMULATION',
            'DEVICE_CONNECTION', 'DEPLOYMENT', 'PHYSICAL_BEHAVIOR',
            'USER_ACCEPTANCE', 'REPRODUCTION', 'STRUCTURE_CHECK'
          )),
          status TEXT NOT NULL CHECK (status IN ('CURRENT', 'STALE', 'FAILED', 'SUPERSEDED')),
          passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
          summary TEXT NOT NULL,
          bindings_json TEXT NOT NULL,
          source_id TEXT NULL,
          recorded_at TEXT NOT NULL,
          invalidated_at TEXT NULL,
          invalidation_reason TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_evidence_project
          ON creator_evidence(project_id, recorded_at DESC);

        CREATE TABLE IF NOT EXISTS creator_commands (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          command TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          base_project_version INTEGER NOT NULL,
          result_project_version INTEGER NOT NULL,
          response_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(project_id, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_commands_project
          ON creator_commands(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS creator_events (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_events_project
          ON creator_events(project_id, created_at ASC);

        CREATE TABLE IF NOT EXISTS creator_system_metrics (
          id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL CHECK (event_type = 'METRIC'),
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS creator_jobs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          solution_revision_id TEXT NOT NULL
            REFERENCES creator_solution_revisions(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK (
            kind IN ('CODE_PREPARATION', 'DIGITAL_PROTOTYPE', 'STRUCTURE_DRAFT')
          ),
          status TEXT NOT NULL CHECK (
            status IN (
              'QUEUED', 'RUNNING', 'WAITING_CONFIRMATION',
              'SUCCEEDED', 'FAILED', 'CANCELED'
            )
          ),
          progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
          message TEXT NULL,
          result_json TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          started_at TEXT NULL,
          completed_at TEXT NULL,
          UNIQUE(solution_revision_id, kind)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_jobs_project
          ON creator_jobs(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS creator_physical_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          solution_revision_id TEXT NOT NULL REFERENCES creator_solution_revisions(id) ON DELETE RESTRICT,
          deployment_operation_id TEXT NOT NULL REFERENCES device_operations(id) ON DELETE RESTRICT,
          target_id TEXT NOT NULL,
          operator TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('PASSED', 'FAILED')),
          emergency_stop_verified INTEGER NOT NULL CHECK (emergency_stop_verified IN (0, 1)),
          scenario_results_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_physical_runs_project
          ON creator_physical_runs(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS creator_deliveries (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          variant TEXT NOT NULL CHECK (variant IN ('SHARE', 'REPRODUCIBLE', 'TEMPLATE')),
          title TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          privacy_report_json TEXT NOT NULL,
          base_package_id TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_deliveries_project
          ON creator_deliveries(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS creator_delivery_imports (
          id TEXT PRIMARY KEY,
          source_delivery_id TEXT NOT NULL,
          source_project_id TEXT NOT NULL,
          imported_project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          importer TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_delivery_imports_project
          ON creator_delivery_imports(imported_project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS creator_delivery_import_intents (
          id TEXT PRIMARY KEY,
          importer_subject TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          imported_project_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PREPARING'
            CHECK (status IN ('PREPARING', 'RECOVERED')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(importer_subject, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_creator_import_intents_project
          ON creator_delivery_import_intents(imported_project_id);

        CREATE TABLE IF NOT EXISTS creator_reproductions (
          id TEXT PRIMARY KEY,
          source_project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          delivery_id TEXT NOT NULL REFERENCES creator_deliveries(id) ON DELETE RESTRICT,
          import_id TEXT NOT NULL REFERENCES creator_delivery_imports(id) ON DELETE RESTRICT,
          reproduced_project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          operator TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('PASSED', 'FAILED')),
          created_at TEXT NOT NULL,
          UNIQUE(source_project_id, import_id)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_reproductions_project
          ON creator_reproductions(source_project_id, created_at DESC);
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO creator_work_state (
          project_id, creator_version, origin, last_stage, created_at, updated_at
        )
        SELECT id, 0, 'LEGACY', 'IDEA_SOLUTION', created_at, updated_at
        FROM projects
        """
    )
    conn.execute("PRAGMA user_version=30")


def _migrate_v31(conn: sqlite3.Connection) -> None:
    """Add durable conversation-to-Creator projection provenance."""

    now = datetime.now(UTC).isoformat()
    for table in ("creator_goal_revisions", "creator_solution_revisions"):
        _add_column(
            conn,
            table,
            "source_type",
            "TEXT NOT NULL DEFAULT 'SYSTEM_MIGRATION'",
        )
        _add_column(conn, table, "source_turn_id", "TEXT NULL")
        _add_column(conn, table, "base_revision_id", "TEXT NULL")
        _add_column(conn, table, "projection_receipt_id", "TEXT NULL")
    _add_column(conn, "creator_solution_revisions", "source_message_id", "TEXT NULL")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creator_projection_receipts (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          source_type TEXT NOT NULL CHECK (
            source_type IN (
              'CONVERSATION', 'PROFESSIONAL_EDIT',
              'LEGACY_PROJECTION', 'SYSTEM_MIGRATION'
            )
          ),
          source_message_id TEXT NOT NULL,
          source_turn_id TEXT NULL,
          draft_hash TEXT NOT NULL,
          status TEXT NOT NULL CHECK (
            status IN ('APPLIED', 'DUPLICATE', 'CONFLICT', 'REJECTED')
          ),
          goal_revision_id TEXT NULL
            REFERENCES creator_goal_revisions(id) ON DELETE SET NULL,
          solution_revision_id TEXT NULL
            REFERENCES creator_solution_revisions(id) ON DELETE SET NULL,
          message TEXT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(project_id, source_message_id)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_projection_receipts_project
          ON creator_projection_receipts(project_id, created_at DESC);
        """
    )
    conn.execute(
        """
        UPDATE creator_goal_revisions
        SET source_type = CASE
          WHEN source_message_id IS NOT NULL THEN 'CONVERSATION'
          ELSE 'SYSTEM_MIGRATION'
        END
        WHERE source_type = 'SYSTEM_MIGRATION'
        """
    )
    conn.execute(
        """
        UPDATE creator_solution_revisions
        SET source_type = CASE
          WHEN source_proposal_id IS NOT NULL THEN 'LEGACY_PROJECTION'
          ELSE 'SYSTEM_MIGRATION'
        END
        WHERE source_type = 'SYSTEM_MIGRATION'
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migration_audit (
          id, from_version, to_version, status, backup_path, applied_at
        ) VALUES ('migration_v30_v31', 30, 31, 'applied', NULL, ?)
        """,
        (now,),
    )
    conn.execute("PRAGMA user_version=31")


def _repair_v31_creator_code_variants(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creator_code_variant_bindings (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          solution_revision_id TEXT NOT NULL
            REFERENCES creator_solution_revisions(id) ON DELETE CASCADE,
          deployment_channel TEXT NOT NULL CHECK (
            deployment_channel IN ('USB_SERIAL', 'ESP_CLAW')
          ),
          runtime TEXT NOT NULL CHECK (
            runtime IN ('MICROPYTHON', 'ESP_CLAW_LUA')
          ),
          code_run_id TEXT NULL REFERENCES code_runs(id) ON DELETE SET NULL,
          device_package_id TEXT NULL,
          validation_status TEXT NOT NULL CHECK (
            validation_status IN (
              'PENDING', 'READY_FOR_REVIEW', 'FAILED', 'ACCEPTED'
            )
          ),
          failure_code TEXT NULL,
          failure_message TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(solution_revision_id, deployment_channel)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_code_variants_project
          ON creator_code_variant_bindings(project_id, updated_at DESC);
        """
    )


def _legacy_snapshot_spec(
    conn: sqlite3.Connection,
) -> list[tuple[str, tuple[str, ...]]]:
    """Freeze the pre-V30 historical tables and columns for a lossless check."""

    tables = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
              AND name NOT LIKE 'creator_%'
              AND name != 'schema_migration_audit'
            ORDER BY name
            """
        ).fetchall()
    ]
    return [
        (
            table,
            tuple(
                str(row[1])
                for row in conn.execute(
                    f'PRAGMA table_info("{table.replace(chr(34), chr(34) * 2)}")'
                ).fetchall()
            ),
        )
        for table in tables
    ]


def _legacy_snapshot_digest(
    conn: sqlite3.Connection,
    spec: list[tuple[str, tuple[str, ...]]],
) -> tuple[str, int]:
    digest = hashlib.sha256()
    row_count = 0
    for table, columns in spec:
        quoted_table = table.replace('"', '""')
        quoted_columns = ", ".join(
            f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns
        )
        try:
            rows = conn.execute(
                f'SELECT {quoted_columns} FROM "{quoted_table}" ORDER BY rowid'
            ).fetchall()
        except sqlite3.OperationalError:
            order_by = ", ".join(
                f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns
            )
            rows = conn.execute(
                f'SELECT {quoted_columns} FROM "{quoted_table}" ORDER BY {order_by}'
            ).fetchall()
        digest.update(table.encode("utf-8"))
        digest.update(b"\0")
        digest.update(json.dumps(columns, ensure_ascii=False).encode("utf-8"))
        for row in rows:
            digest.update(
                json.dumps(
                    [_canonical_sql_value(value) for value in row],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            digest.update(b"\n")
            row_count += 1
    return digest.hexdigest(), row_count


def _canonical_sql_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"type": "blob", "hex": value.hex()}
    return {"type": type(value).__name__, "value": value}


def _append_v30_migration_metrics(
    conn: sqlite3.Connection,
    *,
    legacy_digest: str,
    migrated_row_count: int,
) -> None:
    from zhangwen.creator.metrics import (
        LegacyMigrationFinishedMetric,
        WorkCreatedMetric,
        append_creator_metric,
        append_creator_system_metric,
        metric_trigger_id,
    )

    project_ids = [
        str(row[0])
        for row in conn.execute("SELECT id FROM projects ORDER BY id").fetchall()
    ]
    for project_id in project_ids:
        append_creator_metric(
            conn,
            project_id,
            WorkCreatedMetric(
                triggerId=metric_trigger_id(
                    metric="WORK_CREATED",
                    project_id=project_id,
                    source_key=f"legacy-v29:{legacy_digest}",
                ),
                origin="LEGACY",
            ),
        )
    append_creator_system_metric(
        conn,
        LegacyMigrationFinishedMetric(
            triggerId=metric_trigger_id(
                metric="LEGACY_MIGRATION_FINISHED",
                project_id="database",
                source_key=f"v29-v30:{legacy_digest}",
            ),
            fromSchemaVersion=29,
            migratedRowCount=migrated_row_count,
            zeroDataLoss=True,
            passed=True,
        ),
    )


def _repair_v30_creator_core_projections(conn: sqlite3.Connection) -> None:
    """Add durable Creator jobs to stores already marked as V30."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creator_system_metrics (
          id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL CHECK (event_type = 'METRIC'),
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS creator_jobs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          solution_revision_id TEXT NOT NULL
            REFERENCES creator_solution_revisions(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK (
            kind IN ('CODE_PREPARATION', 'DIGITAL_PROTOTYPE', 'STRUCTURE_DRAFT')
          ),
          status TEXT NOT NULL CHECK (
            status IN (
              'QUEUED', 'RUNNING', 'WAITING_CONFIRMATION',
              'SUCCEEDED', 'FAILED', 'CANCELED'
            )
          ),
          progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
          message TEXT NULL,
          result_json TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          started_at TEXT NULL,
          completed_at TEXT NULL,
          UNIQUE(solution_revision_id, kind)
        );

        CREATE INDEX IF NOT EXISTS idx_creator_jobs_project
          ON creator_jobs(project_id, updated_at DESC);
        """
    )


def _repair_v30_creator_physical_runs(conn: sqlite3.Connection) -> None:
    """Add immutable physical acceptance reports to already-created V30 stores."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creator_physical_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          solution_revision_id TEXT NOT NULL REFERENCES creator_solution_revisions(id) ON DELETE RESTRICT,
          deployment_operation_id TEXT NOT NULL REFERENCES device_operations(id) ON DELETE RESTRICT,
          target_id TEXT NOT NULL,
          operator TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('PASSED', 'FAILED')),
          emergency_stop_verified INTEGER NOT NULL CHECK (emergency_stop_verified IN (0, 1)),
          scenario_results_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_creator_physical_runs_project
          ON creator_physical_runs(project_id, created_at DESC);
        """
    )


def _repair_v30_creator_deliveries(conn: sqlite3.Connection) -> None:
    """Add Creator delivery/import/reproduction records to existing V30 stores."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creator_deliveries (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          variant TEXT NOT NULL CHECK (variant IN ('SHARE', 'REPRODUCIBLE', 'TEMPLATE')),
          title TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          privacy_report_json TEXT NOT NULL,
          base_package_id TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_creator_deliveries_project
          ON creator_deliveries(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS creator_delivery_imports (
          id TEXT PRIMARY KEY,
          source_delivery_id TEXT NOT NULL,
          source_project_id TEXT NOT NULL,
          imported_project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          importer TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_creator_delivery_imports_project
          ON creator_delivery_imports(imported_project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS creator_delivery_import_intents (
          id TEXT PRIMARY KEY,
          importer_subject TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          imported_project_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PREPARING'
            CHECK (status IN ('PREPARING', 'RECOVERED')),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(importer_subject, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_creator_import_intents_project
          ON creator_delivery_import_intents(imported_project_id);

        CREATE TABLE IF NOT EXISTS creator_reproductions (
          id TEXT PRIMARY KEY,
          source_project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          delivery_id TEXT NOT NULL REFERENCES creator_deliveries(id) ON DELETE RESTRICT,
          import_id TEXT NOT NULL REFERENCES creator_delivery_imports(id) ON DELETE RESTRICT,
          reproduced_project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          operator TEXT NOT NULL,
          package_sha256 TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('PASSED', 'FAILED')),
          created_at TEXT NOT NULL,
          UNIQUE(source_project_id, import_id)
        );
        CREATE INDEX IF NOT EXISTS idx_creator_reproductions_project
          ON creator_reproductions(source_project_id, created_at DESC);
        """
    )


def _repair_v30_creator_idempotency(conn: sqlite3.Connection) -> None:
    """Backfill durable request identities without changing the V30 file format."""

    for table, name, declaration in (
        ("device_lab_runs", "idempotency_key", "TEXT NULL"),
        ("device_lab_runs", "request_hash", "TEXT NULL"),
        ("device_parameter_sets", "idempotency_key", "TEXT NULL"),
        ("device_parameter_sets", "request_hash", "TEXT NULL"),
        ("creator_physical_runs", "idempotency_key", "TEXT NULL"),
        ("creator_physical_runs", "request_hash", "TEXT NULL"),
        ("creator_physical_runs", "operator_subject", "TEXT NULL"),
        ("creator_deliveries", "idempotency_key", "TEXT NULL"),
        ("creator_deliveries", "request_hash", "TEXT NULL"),
        ("creator_deliveries", "actor_subject", "TEXT NULL"),
        ("creator_deliveries", "zip_base64", "TEXT NULL"),
        ("creator_deliveries", "file_name", "TEXT NULL"),
        ("creator_delivery_imports", "idempotency_key", "TEXT NULL"),
        ("creator_delivery_imports", "request_hash", "TEXT NULL"),
        ("creator_delivery_imports", "importer_subject", "TEXT NULL"),
        ("creator_delivery_imports", "id_map_json", "TEXT NULL"),
        (
            "creator_delivery_import_intents",
            "status",
            "TEXT NOT NULL DEFAULT 'PREPARING'",
        ),
        ("creator_reproductions", "operator_subject", "TEXT NULL"),
    ):
        _add_column(conn, table, name, declaration)
    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_device_lab_runs_idempotency
          ON device_lab_runs(project_id, idempotency_key)
          WHERE idempotency_key IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_device_parameter_sets_idempotency
          ON device_parameter_sets(project_id, idempotency_key)
          WHERE idempotency_key IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_physical_runs_idempotency
          ON creator_physical_runs(project_id, idempotency_key)
          WHERE idempotency_key IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_deliveries_idempotency
          ON creator_deliveries(project_id, idempotency_key)
          WHERE idempotency_key IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_imports_idempotency
          ON creator_delivery_imports(importer_subject, idempotency_key)
          WHERE importer_subject IS NOT NULL AND idempotency_key IS NOT NULL;
        """
    )


def _repair_v29_device_lab_scene_table(conn: sqlite3.Connection) -> None:
    """Add the corrected proposal-derived scene projection to existing V29 stores."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS device_lab_scenes (
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          revision TEXT NOT NULL,
          proposal_id TEXT NOT NULL,
          proposal_version INTEGER NOT NULL,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('seeedstudio/xiao_esp32s3_sense', 'dfrobot/dfrobot_k10')
          ),
          scene_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(project_id, revision)
        );

        CREATE INDEX IF NOT EXISTS idx_device_lab_scenes_project
          ON device_lab_scenes(project_id, created_at DESC);
        """
    )


def _repair_v29_espclaw_tables(conn: sqlite3.Connection) -> None:
    """Create code-deployment endpoint state for stores already marked V29."""

    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    deployment_rows: list[dict[str, object]] = []
    if "espclaw_endpoints" in tables:
        columns = [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(espclaw_endpoints)").fetchall()
        ]
        table_sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='espclaw_endpoints'"
        ).fetchone()
        normalized_sql = "".join(str(table_sql_row[0] if table_sql_row else "").lower().split())
        canonical_unique = (
            "unique(project_id,web_endpoint)" in normalized_sql
            and "unique(project_id,web_endpoint,mcp_endpoint)" not in normalized_sql
        )
        needs_rebuild = (
            "endpoint_url" in columns
            or "web_endpoint" not in columns
            or "mcp_endpoint" not in columns
            or not canonical_unique
        )
        if needs_rebuild:
            if "espclaw_deployments" in tables:
                deployment_columns = [
                    str(row[1])
                    for row in conn.execute(
                        "PRAGMA table_info(espclaw_deployments)"
                    ).fetchall()
                ]
                deployment_rows = [
                    dict(zip(deployment_columns, row, strict=True))
                    for row in conn.execute(
                        "SELECT * FROM espclaw_deployments"
                    ).fetchall()
                ]
                conn.execute("DROP TABLE espclaw_deployments")
            endpoint_rows = [
                dict(zip(columns, row, strict=True))
                for row in conn.execute(
                    "SELECT * FROM espclaw_endpoints ORDER BY updated_at DESC"
                ).fetchall()
            ]
            conn.execute("DROP TABLE IF EXISTS espclaw_endpoints_v29_repair")
            conn.execute(
                """
                CREATE TABLE espclaw_endpoints_v29_repair (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                  session_id TEXT NOT NULL UNIQUE REFERENCES device_sessions(id) ON DELETE CASCADE,
                  web_endpoint TEXT NOT NULL,
                  mcp_endpoint TEXT NOT NULL,
                  board_id TEXT NOT NULL CHECK (
                    board_id IN ('dfrobot/dfrobot_k10', 'seeedstudio/xiao_esp32s3_sense')
                  ),
                  status TEXT NOT NULL CHECK (status IN ('READY', 'ERROR')),
                  storage_base_path TEXT NOT NULL CHECK (storage_base_path = '/fatfs'),
                  capabilities_json TEXT NOT NULL,
                  paired_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(project_id, web_endpoint)
                )
                """
            )
            legacy_shape = "endpoint_url" in columns
            for row in endpoint_rows:
                web_endpoint = row.get("web_endpoint") or row.get("endpoint_url")
                mcp_endpoint = row.get("mcp_endpoint") or row.get("endpoint_url")
                if not web_endpoint or not mcp_endpoint:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO espclaw_endpoints_v29_repair (
                      id, project_id, session_id, web_endpoint, mcp_endpoint,
                      board_id, status, storage_base_path, capabilities_json,
                      paired_at, last_seen_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["project_id"],
                        row["session_id"],
                        web_endpoint,
                        mcp_endpoint,
                        row["board_id"],
                        "ERROR" if legacy_shape else row["status"],
                        row["storage_base_path"],
                        row["capabilities_json"],
                        row["paired_at"],
                        row["last_seen_at"],
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            conn.execute("DROP TABLE espclaw_endpoints")
            conn.execute(
                "ALTER TABLE espclaw_endpoints_v29_repair RENAME TO espclaw_endpoints"
            )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS espclaw_endpoints (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          session_id TEXT NOT NULL UNIQUE REFERENCES device_sessions(id) ON DELETE CASCADE,
          web_endpoint TEXT NOT NULL,
          mcp_endpoint TEXT NOT NULL,
          board_id TEXT NOT NULL CHECK (
            board_id IN ('dfrobot/dfrobot_k10', 'seeedstudio/xiao_esp32s3_sense')
          ),
          status TEXT NOT NULL CHECK (status IN ('READY', 'ERROR')),
          storage_base_path TEXT NOT NULL CHECK (storage_base_path = '/fatfs'),
          capabilities_json TEXT NOT NULL,
          paired_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(project_id, web_endpoint)
        );

        CREATE INDEX IF NOT EXISTS idx_espclaw_endpoints_project
          ON espclaw_endpoints(project_id, last_seen_at DESC);

        CREATE TABLE IF NOT EXISTS espclaw_deployments (
          operation_id TEXT PRIMARY KEY REFERENCES device_operations(id) ON DELETE CASCADE,
          endpoint_id TEXT NOT NULL REFERENCES espclaw_endpoints(id) ON DELETE CASCADE,
          code_run_id TEXT NOT NULL,
          version_path TEXT NOT NULL,
          entrypoint_path TEXT NOT NULL,
          fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_espclaw_deployments_endpoint
          ON espclaw_deployments(endpoint_id, created_at DESC);
        """
    )
    if deployment_rows:
        kept_endpoint_ids = {
            str(row[0])
            for row in conn.execute("SELECT id FROM espclaw_endpoints").fetchall()
        }
        for row in deployment_rows:
            if str(row.get("endpoint_id")) not in kept_endpoint_ids:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO espclaw_deployments (
                  operation_id, endpoint_id, code_run_id, version_path,
                  entrypoint_path, fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("operation_id"),
                    row.get("endpoint_id"),
                    row.get("code_run_id"),
                    row.get("version_path"),
                    row.get("entrypoint_path"),
                    row.get("fingerprint"),
                    row.get("created_at"),
                ),
            )


def _repair_code_run_runtime_columns(conn: sqlite3.Connection) -> None:
    """Keep V29 while adding explicit runtime identity to old and new CodeRuns."""

    if "code_runs" not in {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }:
        return
    _add_column(
        conn,
        "code_runs",
        "runtime",
        "TEXT NOT NULL DEFAULT 'MICROPYTHON'",
    )
    _add_column(
        conn,
        "code_runs",
        "entrypoint",
        "TEXT NOT NULL DEFAULT 'src/main.py'",
    )
    conn.execute(
        """
        UPDATE code_runs
        SET runtime = 'MICROPYTHON'
        WHERE runtime IS NULL OR TRIM(runtime) = ''
        """
    )
    conn.execute(
        """
        UPDATE code_runs
        SET entrypoint = CASE runtime
          WHEN 'ESP_CLAW_LUA' THEN 'scripts/main.lua'
          ELSE 'src/main.py'
        END
        WHERE entrypoint IS NULL OR TRIM(entrypoint) = ''
        """
    )


def _execute_sql_script(conn: sqlite3.Connection, script: str) -> None:
    """Execute statements without sqlite3.executescript's implicit commits."""

    pending: list[str] = []
    for line in script.splitlines():
        pending.append(line)
        statement = "\n".join(pending)
        if sqlite3.complete_statement(statement):
            if statement.strip():
                conn.execute(statement)
            pending.clear()
    if pending and "".join(pending).strip():
        raise sqlite3.OperationalError("incomplete migration SQL statement")


def _assert_foreign_keys_clean(conn: sqlite3.Connection) -> None:
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        details = "; ".join(
            ",".join(str(value) for value in violation) for violation in violations[:8]
        )
        raise sqlite3.IntegrityError(
            f"project database foreign-key check failed: {details}"
        )


def _remove_conversation_project_unique(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "project_id" not in columns:
        return
    indexes = conn.execute("PRAGMA index_list(conversations)").fetchall()
    has_project_unique = False
    for index in indexes:
        index_name = index[1]
        is_unique = bool(index[2])
        if not is_unique:
            continue
        indexed_columns = [
            column[2]
            for column in conn.execute(f"PRAGMA index_info({index_name})").fetchall()
        ]
        if indexed_columns == ["project_id"]:
            has_project_unique = True
            break
    if not has_project_unique:
        return
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.executescript(
        """
        CREATE TABLE conversations_v17 (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        INSERT INTO conversations_v17 (id, project_id, created_at, updated_at)
        SELECT id, project_id, created_at, updated_at FROM conversations;

        DROP TABLE conversations;
        ALTER TABLE conversations_v17 RENAME TO conversations;

        CREATE INDEX IF NOT EXISTS idx_conversations_project
          ON conversations(project_id, updated_at);
        """
    )
    conn.execute("PRAGMA foreign_keys=ON")


def _add_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = _table_columns(conn, table)
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _rebuild_project_experts_v19(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "project_experts")
    if not columns:
        return
    legacy_expr = (
        "legacy_expert_type"
        if "legacy_expert_type" in columns
        else """
        CASE
          WHEN expert_type IN (
            'question_guide',
            'intelligent_engineer',
            'ideator',
            'educator',
            'open_hardware_designer',
            'structure_designer',
            'three_d_structure_designer'
          ) THEN expert_type
          ELSE NULL
        END
        """
    )
    archived_expr = (
        "archived_legacy_thread"
        if "archived_legacy_thread" in columns
        else """
        CASE
          WHEN expert_type IN (
            'ideator',
            'educator',
            'open_hardware_designer',
            'structure_designer',
            'three_d_structure_designer'
          ) OR removed_at IS NOT NULL THEN 1
          ELSE 0
        END
        """
    )
    workspace_expr = (
        "workspace_status"
        if "workspace_status" in columns
        else """
        CASE status
          WHEN 'waiting_user' THEN 'awaiting_user'
          WHEN 'working' THEN 'in_progress'
          WHEN 'blocked' THEN 'waiting_dependency'
          WHEN 'completed' THEN 'completed'
          ELSE 'not_started'
        END
        """
    )
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DROP TABLE IF EXISTS project_experts_v19")
    conn.executescript(
        """
        CREATE TABLE project_experts_v19 (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          expert_definition_id TEXT NOT NULL REFERENCES expert_definitions(id) ON DELETE RESTRICT,
          expert_type TEXT NOT NULL,
          legacy_expert_type TEXT NULL,
          archived_legacy_thread INTEGER NOT NULL DEFAULT 0,
          conversation_id TEXT NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE RESTRICT,
          private_memory_id TEXT NOT NULL,
          status TEXT NOT NULL,
          workspace_status TEXT NULL,
          current_task TEXT NULL,
          added_at TEXT NOT NULL,
          removed_at TEXT NULL
        );
        """
    )
    conn.execute(
        f"""
        INSERT INTO project_experts_v19 (
          id, project_id, expert_definition_id, expert_type, legacy_expert_type,
          archived_legacy_thread, conversation_id, private_memory_id, status,
          workspace_status, current_task, added_at, removed_at
        )
        SELECT
          id, project_id, expert_definition_id, expert_type, {legacy_expr},
          COALESCE({archived_expr}, 0), conversation_id, private_memory_id, status,
          {workspace_expr}, current_task, added_at, removed_at
        FROM project_experts
        """
    )
    conn.executescript(
        """
        DROP TABLE project_experts;
        ALTER TABLE project_experts_v19 RENAME TO project_experts;

        CREATE INDEX IF NOT EXISTS idx_project_experts_project
          ON project_experts(project_id, removed_at, archived_legacy_thread, expert_type);

        CREATE INDEX IF NOT EXISTS idx_project_experts_legacy
          ON project_experts(project_id, legacy_expert_type, archived_legacy_thread);
        """
    )
    conn.execute("PRAGMA foreign_keys=ON")


def _create_three_expert_domain_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_shared_facts (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          field TEXT NOT NULL,
          value_json TEXT NOT NULL,
          status TEXT NOT NULL,
          source_type TEXT NOT NULL,
          source_id TEXT NULL,
          source_expert_id TEXT NULL,
          proposed_by_expert_type TEXT NULL,
          confirmed_by TEXT NULL,
          confirmed_at TEXT NULL,
          superseded_by TEXT NULL,
          affects_artifact_ids_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_shared_facts_project
          ON project_shared_facts(project_id, status, updated_at);

        CREATE TABLE IF NOT EXISTS project_decisions (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          value_json TEXT NOT NULL,
          status TEXT NOT NULL,
          reason TEXT NOT NULL,
          proposed_by_expert_type TEXT NULL,
          confirmed_by TEXT NULL,
          confirmed_at TEXT NULL,
          affected_artifact_ids_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_decisions_project
          ON project_decisions(project_id, status, updated_at);

        CREATE TABLE IF NOT EXISTS project_pending_items (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL,
          priority TEXT NOT NULL,
          reason TEXT NOT NULL,
          affected_experts_json TEXT NOT NULL,
          options_json TEXT NOT NULL,
          status TEXT NOT NULL,
          is_highlighted INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_pending_items_project
          ON project_pending_items(project_id, status, priority, updated_at);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_project_pending_items_one_highlight
          ON project_pending_items(project_id)
          WHERE is_highlighted = 1 AND status = 'open';

        CREATE TABLE IF NOT EXISTS project_handoffs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          from_expert_type TEXT NOT NULL,
          to_expert_type TEXT NOT NULL,
          handoff_type TEXT NOT NULL,
          status TEXT NOT NULL,
          summary TEXT NULL,
          confirmed_requirements_json TEXT NOT NULL,
          shared_fact_ids_json TEXT NOT NULL,
          related_artifact_ids_json TEXT NOT NULL,
          required_outputs_json TEXT NOT NULL,
          dependencies_json TEXT NOT NULL,
          open_questions_json TEXT NOT NULL,
          current_pending_item_id TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_handoffs_project
          ON project_handoffs(project_id, status, updated_at);

        CREATE TABLE IF NOT EXISTS artifact_dependencies (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
          artifact_version_id TEXT NOT NULL REFERENCES artifact_versions(id) ON DELETE CASCADE,
          upstream_artifact_id TEXT NOT NULL,
          upstream_version_id TEXT NULL,
          upstream_version INTEGER NULL,
          relation TEXT NOT NULL,
          kind TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          required INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_artifact_dependencies_project
          ON artifact_dependencies(project_id, artifact_id, upstream_artifact_id);
        """
    )


def _seed_expert_definitions(conn: sqlite3.Connection) -> None:
    experts = [
        (
            "expert_def_problem_guide",
            "problem_guide",
            "问题引导师",
            "从困惑到方案，负责创意引导、需求澄清、项目立项、实验方案和教学设计。",
            "spark",
            [
                "idea-understanding",
                "requirement-clarification",
                "problem-definition",
                "experiment-design",
                "pbl-lesson-planning",
                "user-journey",
                "concept-expression",
            ],
            [
                "concept",
                "requirements",
                "implementation_solution",
                "project_brief",
                "experiment_plan",
                "lesson_plan",
                "student_worksheet",
                "assessment",
            ],
        ),
        (
            "expert_def_smart_engineer",
            "smart_engineer",
            "智能工程师",
            "负责硬件、软件、IoT、数据与 AI 部署，用工程技术实现项目想法。",
            "cpu",
            [
                "hardware-selection",
                "bom-generation",
                "io-map",
                "wiring",
                "electrical-check",
                "micropython-generation",
                "arduino-generation",
                "code-review",
                "mock-test",
                "iot-mqtt",
                "iot-http",
                "data-acquisition",
                "data-analysis",
                "ai-deployment",
                "vision-inference",
                "project-packaging",
            ],
            [
                "hardware_solution",
                "bom",
                "io_map",
                "wiring",
                "electrical_check_report",
                "micropython_project",
                "arduino_project",
                "micropython_test_report",
                "iot_config",
                "mqtt_protocol",
                "data_model",
                "data_analysis_result",
                "ai_deployment",
                "project_package",
            ],
        ),
        (
            "expert_def_structure_engineer",
            "structure_engineer",
            "结构工程师",
            "将想法塑造成实物，负责外观、装配、结构件和可打印性。",
            "box",
            [
                "dimension-reading",
                "parametric-modeling",
                "enclosure-design",
                "assembly-check",
            ],
            [
                "appearance_design",
                "structure_design",
                "dimension_table",
                "component_layout",
                "assembly_plan",
                "cad_model",
                "stl",
                "step",
                "3mf",
                "print_settings",
                "printability_report",
            ],
        ),
    ]
    for expert in experts:
        expert_id, expert_type, name, description, icon, skill_ids, artifact_types = expert
        conn.execute(
            """
            INSERT INTO expert_definitions (
              id, expert_type, name, description, icon, built_in,
              skill_ids_json, supported_artifact_types_json
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(expert_type) DO UPDATE SET
              name = excluded.name,
              description = excluded.description,
              icon = excluded.icon,
              built_in = excluded.built_in,
              skill_ids_json = excluded.skill_ids_json,
              supported_artifact_types_json = excluded.supported_artifact_types_json
            """,
            (
                expert_id,
                expert_type,
                name,
                description,
                icon,
                json.dumps(skill_ids, ensure_ascii=False),
                json.dumps(artifact_types, ensure_ascii=False),
            ),
        )


def _normalize_legacy_project_experts(conn: sqlite3.Connection) -> None:
    now = _now()
    project_rows = conn.execute("SELECT id, active_expert_id FROM projects").fetchall()
    for project_id, active_expert_id in project_rows:
        rows = conn.execute(
            """
            SELECT id, expert_type, removed_at
            FROM project_experts
            WHERE project_id = ?
            ORDER BY added_at ASC
            """,
            (project_id,),
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            canonical = _canonical_expert_type(str(row[1]))
            grouped.setdefault(canonical, []).append(row)

        for canonical_type, expert_rows in grouped.items():
            definition = conn.execute(
                "SELECT id FROM expert_definitions WHERE expert_type = ?",
                (canonical_type,),
            ).fetchone()
            if definition is None:
                continue
            keeper = _choose_keeper(
                expert_rows,
                canonical_type,
                str(active_expert_id or ""),
            )
            keeper_id = str(keeper[0])
            conn.execute(
                """
                UPDATE project_experts
                SET expert_definition_id = ?, expert_type = ?, removed_at = NULL
                WHERE id = ?
                """,
                (str(definition[0]), canonical_type, keeper_id),
            )
            for row in expert_rows:
                expert_id = str(row[0])
                if expert_id == keeper_id:
                    continue
                conn.execute(
                    """
                    UPDATE project_experts
                    SET removed_at = COALESCE(removed_at, ?)
                    WHERE id = ?
                    """,
                    (now, expert_id),
                )
                conn.execute(
                    """
                    UPDATE artifacts
                    SET owner_expert_id = ?, owner_expert_type = ?
                    WHERE project_id = ? AND owner_expert_id = ?
                    """,
                    (keeper_id, canonical_type, project_id, expert_id),
                )

        active_row = conn.execute(
            """
            SELECT id FROM project_experts
            WHERE project_id = ? AND id = ? AND removed_at IS NULL
            """,
            (project_id, active_expert_id),
        ).fetchone()
        if active_row is not None:
            continue
        fallback = conn.execute(
            """
            SELECT id FROM project_experts
            WHERE project_id = ? AND removed_at IS NULL
            ORDER BY CASE expert_type
              WHEN 'problem_guide' THEN 1
              WHEN 'smart_engineer' THEN 2
              WHEN 'structure_engineer' THEN 3
              ELSE 99
            END, added_at ASC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if fallback is not None:
            conn.execute(
                "UPDATE projects SET active_expert_id = ? WHERE id = ?",
                (str(fallback[0]), project_id),
            )


def _choose_keeper(
    rows: list[sqlite3.Row],
    canonical_type: str,
    active_expert_id: str,
) -> sqlite3.Row:
    canonical = next((row for row in rows if str(row[1]) == canonical_type), None)
    if canonical is not None:
        return canonical
    active = next((row for row in rows if str(row[0]) == active_expert_id), None)
    if active is not None:
        return active
    visible = next((row for row in rows if row[2] is None), None)
    return visible or rows[0]


def _normalize_legacy_artifact_owners(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE artifacts
        SET owner_expert_type = CASE owner_expert_type
          WHEN 'question_guide' THEN 'problem_guide'
          WHEN 'intelligent_engineer' THEN 'smart_engineer'
          WHEN 'ideator' THEN 'problem_guide'
          WHEN 'educator' THEN 'problem_guide'
          WHEN 'open_hardware_designer' THEN 'smart_engineer'
          WHEN 'structure_designer' THEN 'structure_engineer'
          WHEN 'three_d_structure_designer' THEN 'structure_engineer'
          ELSE owner_expert_type
        END
        WHERE owner_expert_type IN (
          'question_guide',
          'intelligent_engineer',
          'ideator',
          'educator',
          'open_hardware_designer',
          'structure_designer',
          'three_d_structure_designer'
        )
        """
    )


def _canonical_expert_type(expert_type: str) -> str:
    return {
        "question_guide": "problem_guide",
        "intelligent_engineer": "smart_engineer",
        "ideator": "problem_guide",
        "educator": "problem_guide",
        "open_hardware_designer": "smart_engineer",
        "structure_designer": "structure_engineer",
        "three_d_structure_designer": "structure_engineer",
    }.get(expert_type, expert_type)


def _is_legacy_expert_type(expert_type: str) -> bool:
    return expert_type in {
        "ideator",
        "educator",
        "open_hardware_designer",
        "structure_designer",
        "three_d_structure_designer",
    }


def _is_transition_expert_type(expert_type: str) -> bool:
    return expert_type in {"question_guide", "intelligent_engineer"} or _is_legacy_expert_type(
        expert_type
    )


def _normalize_expert_rows_v19(conn: sqlite3.Connection) -> None:
    now = _now()
    definitions = {
        str(row[0]): str(row[1])
        for row in conn.execute(
            "SELECT expert_type, id FROM expert_definitions"
        ).fetchall()
    }
    rows = conn.execute(
        """
        SELECT id, project_id, expert_type, legacy_expert_type,
               archived_legacy_thread, removed_at, conversation_id, status
        FROM project_experts
        ORDER BY project_id, added_at ASC
        """
    ).fetchall()
    for row in rows:
        expert_id = str(row[0])
        original_type = str(row[2])
        canonical_type = _canonical_expert_type(original_type)
        legacy_type = row[3]
        if legacy_type is None and original_type != canonical_type and _is_transition_expert_type(
            original_type
        ):
            legacy_type = original_type
        archived = bool(row[4]) or _is_legacy_expert_type(original_type)
        definition_id = definitions.get(canonical_type)
        if definition_id is None:
            continue
        conn.execute(
            """
            UPDATE project_experts
            SET expert_definition_id = ?,
                expert_type = ?,
                legacy_expert_type = ?,
                archived_legacy_thread = ?,
                workspace_status = COALESCE(workspace_status, ?)
            WHERE id = ?
            """,
            (
                definition_id,
                canonical_type,
                legacy_type,
                1 if archived else 0,
                _workspace_status_for_project_status(str(row[7])),
                expert_id,
            ),
        )
        conn.execute(
            """
            UPDATE conversations
            SET owner_expert_type = ?,
                legacy_expert_type = ?,
                archived_legacy_thread = ?
            WHERE id = ?
            """,
            (
                canonical_type,
                legacy_type,
                1 if archived else 0,
                str(row[6]),
            ),
        )
        if archived and row[5] is None:
            conn.execute(
                "UPDATE project_experts SET removed_at = ? WHERE id = ?",
                (now, expert_id),
            )


def _workspace_status_for_project_status(status: str) -> str:
    return {
        "waiting_user": "awaiting_user",
        "working": "in_progress",
        "blocked": "waiting_dependency",
        "completed": "completed",
    }.get(status, "not_started")


def _ensure_canonical_project_workspaces_v19(conn: sqlite3.Connection) -> None:
    now = _now()
    project_rows = conn.execute("SELECT id, active_expert_id FROM projects").fetchall()
    for project_id, active_expert_id in project_rows:
        project_id = str(project_id)
        desired_types = {"problem_guide"} | _infer_legacy_experts(conn, project_id)
        legacy_rows = conn.execute(
            """
            SELECT expert_type FROM project_experts
            WHERE project_id = ? AND archived_legacy_thread = 1
            """,
            (project_id,),
        ).fetchall()
        desired_types.update(str(row[0]) for row in legacy_rows)
        for expert_type in _ordered_expert_types(desired_types):
            _ensure_project_expert(
                conn,
                project_id=project_id,
                expert_type=expert_type,
                conversation_id=None,
                current_task=_default_task_for_expert(expert_type),
                now=now,
            )

        active_row = None
        if active_expert_id:
            active_row = conn.execute(
                """
                SELECT id FROM project_experts
                WHERE id = ?
                  AND project_id = ?
                  AND removed_at IS NULL
                  AND archived_legacy_thread = 0
                """,
                (str(active_expert_id), project_id),
            ).fetchone()
        if active_row is not None:
            continue
        fallback = conn.execute(
            """
            SELECT id FROM project_experts
            WHERE project_id = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            ORDER BY CASE expert_type
              WHEN 'problem_guide' THEN 1
              WHEN 'smart_engineer' THEN 2
              WHEN 'structure_engineer' THEN 3
              ELSE 99
            END, added_at ASC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if fallback is not None:
            conn.execute(
                "UPDATE projects SET active_expert_id = ? WHERE id = ?",
                (str(fallback[0]), project_id),
            )


def _ordered_expert_types(expert_types: set[str]) -> list[str]:
    order = {
        "problem_guide": 1,
        "smart_engineer": 2,
        "structure_engineer": 3,
    }
    return sorted(expert_types, key=lambda item: (order.get(item, 99), item))


def _normalize_artifact_owners_v19(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE artifacts
        SET legacy_owner_expert = COALESCE(legacy_owner_expert, owner_expert_type),
            creator_legacy_expert = COALESCE(creator_legacy_expert, owner_expert_type)
        WHERE owner_expert_type IS NOT NULL
          AND owner_expert_type NOT IN ('problem_guide', 'smart_engineer', 'structure_engineer')
        """
    )
    rows = conn.execute(
        """
        SELECT id, project_id, status, source_agent_id, owner_expert_type,
               owner_expert_id, source_conversation_id
        FROM artifacts
        """
    ).fetchall()
    for row in rows:
        artifact_id = str(row[0])
        project_id = str(row[1])
        original_owner_type = str(row[4]) if row[4] is not None else None
        owner_type = _canonical_expert_type(
            original_owner_type or _owner_type_for_source_agent(str(row[3]))
        )
        owner_row = conn.execute(
            """
            SELECT id, conversation_id FROM project_experts
            WHERE project_id = ?
              AND expert_type = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            ORDER BY added_at ASC
            LIMIT 1
            """,
            (project_id, owner_type),
        ).fetchone()
        context_row = conn.execute(
            "SELECT revision FROM project_shared_contexts WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        revision = int(context_row[0]) if context_row else 1
        conn.execute(
            """
            UPDATE artifacts
            SET owner_expert_id = ?,
                owner_expert_type = ?,
                source_conversation_id = COALESCE(source_conversation_id, ?),
                shared_context_revision = COALESCE(shared_context_revision, ?),
                domain_status = ?
            WHERE id = ?
            """,
            (
                str(owner_row[0]) if owner_row else None,
                owner_type,
                str(owner_row[1]) if owner_row else None,
                revision,
                _domain_status_for_artifact_status(str(row[2])),
                artifact_id,
            ),
        )
    conn.execute(
        """
        UPDATE artifact_versions
        SET domain_status = CASE status
          WHEN 'DRAFT' THEN 'draft'
          WHEN 'GENERATING' THEN 'pending_confirmation'
          WHEN 'NEEDS_REVIEW' THEN 'pending_confirmation'
          WHEN 'APPROVED' THEN 'confirmed'
          WHEN 'STALE' THEN 'outdated'
          WHEN 'ARCHIVED' THEN 'archived'
          ELSE COALESCE(domain_status, 'pending_confirmation')
        END
        """
    )


def _domain_status_for_artifact_status(status: str) -> str:
    return {
        "DRAFT": "draft",
        "GENERATING": "pending_confirmation",
        "NEEDS_REVIEW": "pending_confirmation",
        "APPROVED": "confirmed",
        "STALE": "outdated",
        "ARCHIVED": "archived",
    }.get(status, "pending_confirmation")


def _normalize_shared_context_v19(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, project_id, goals_json, constraints_json, requirements_json,
               decisions_json, updated_at
        FROM project_shared_contexts
        """
    ).fetchall()
    for row in rows:
        project_id = str(row[1])
        updated_at = str(row[6])
        goals = _normalize_fact_list(project_id, row[2], updated_at)
        constraints = _normalize_fact_list(project_id, row[3], updated_at)
        requirements = _normalize_fact_list(project_id, row[4], updated_at)
        decisions = _normalize_decision_list(project_id, row[5], updated_at)
        conn.execute(
            """
            UPDATE project_shared_contexts
            SET goals_json = ?,
                constraints_json = ?,
                requirements_json = ?,
                decisions_json = ?
            WHERE id = ?
            """,
            (
                json.dumps(goals, ensure_ascii=False),
                json.dumps(constraints, ensure_ascii=False),
                json.dumps(requirements, ensure_ascii=False),
                json.dumps(decisions, ensure_ascii=False),
                str(row[0]),
            ),
        )
        for item in [*goals, *constraints, *requirements]:
            conn.execute(
                """
                INSERT INTO project_shared_facts (
                  id, project_id, field, value_json, status, source_type, source_id,
                  source_expert_id, proposed_by_expert_type, confirmed_by,
                  confirmed_at, superseded_by, affects_artifact_ids_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  field = excluded.field,
                  value_json = excluded.value_json,
                  status = excluded.status,
                  source_type = excluded.source_type,
                  source_id = excluded.source_id,
                  source_expert_id = excluded.source_expert_id,
                  proposed_by_expert_type = excluded.proposed_by_expert_type,
                  confirmed_by = excluded.confirmed_by,
                  confirmed_at = excluded.confirmed_at,
                  superseded_by = excluded.superseded_by,
                  affects_artifact_ids_json = excluded.affects_artifact_ids_json,
                  updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    project_id,
                    item["field"],
                    json.dumps(item["value"], ensure_ascii=False),
                    item["status"],
                    item["sourceType"],
                    item.get("sourceId"),
                    item.get("sourceExpertId"),
                    item.get("proposedBy"),
                    item.get("confirmedBy"),
                    item.get("confirmedAt"),
                    item.get("supersededBy"),
                    json.dumps(item.get("affectsArtifactIds", []), ensure_ascii=False),
                    item["createdAt"],
                    item["updatedAt"],
                ),
            )
        for item in decisions:
            conn.execute(
                """
                INSERT INTO project_decisions (
                  id, project_id, title, value_json, status, reason,
                  proposed_by_expert_type, confirmed_by, confirmed_at,
                  affected_artifact_ids_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  title = excluded.title,
                  value_json = excluded.value_json,
                  status = excluded.status,
                  reason = excluded.reason,
                  proposed_by_expert_type = excluded.proposed_by_expert_type,
                  confirmed_by = excluded.confirmed_by,
                  confirmed_at = excluded.confirmed_at,
                  affected_artifact_ids_json = excluded.affected_artifact_ids_json,
                  updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    project_id,
                    item["title"],
                    json.dumps(item["value"], ensure_ascii=False),
                    item["status"],
                    item["reason"],
                    item.get("proposedBy"),
                    item.get("confirmedBy"),
                    item.get("confirmedAt"),
                    json.dumps(item.get("affectedArtifactIds", []), ensure_ascii=False),
                    item["createdAt"],
                    item["updatedAt"],
                ),
            )


def _normalize_fact_list(
    project_id: str,
    raw_json: str | None,
    updated_at: str,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in _json_array(raw_json):
        field = str(item.get("field") or item.get("key") or "")
        if not field:
            continue
        confirmed_by = item.get("confirmedBy")
        status = str(item.get("status") or "proposed")
        if status == "confirmed" and not confirmed_by:
            status = "proposed"
        confirmed = status == "confirmed"
        normalized.append(
            {
                "id": str(item.get("id") or _id("fact")),
                "projectId": project_id,
                "field": field,
                "key": str(item.get("key") or field),
                "value": item.get("value"),
                "status": "confirmed" if confirmed else status,
                "sourceType": str(item.get("sourceType") or "user"),
                "sourceId": item.get("sourceId"),
                "sourceExpertId": item.get("sourceExpertId"),
                "proposedBy": item.get("proposedBy"),
                "confirmed": confirmed,
                "confirmedBy": confirmed_by if confirmed else None,
                "confirmedAt": item.get("confirmedAt") if confirmed else None,
                "supersededBy": item.get("supersededBy"),
                "affectsArtifactIds": list(item.get("affectsArtifactIds") or []),
                "createdAt": str(item.get("createdAt") or updated_at),
                "updatedAt": str(item.get("updatedAt") or updated_at),
            }
        )
    return normalized


def _normalize_decision_list(
    project_id: str,
    raw_json: str | None,
    updated_at: str,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in _json_array(raw_json):
        title = str(item.get("title") or "")
        if not title:
            continue
        confirmed_at = item.get("confirmedAt")
        normalized.append(
            {
                "id": str(item.get("id") or _id("decision")),
                "projectId": project_id,
                "title": title,
                "value": item.get("value"),
                "status": str(item.get("status") or ("confirmed" if confirmed_at else "proposed")),
                "reason": str(item.get("reason") or ""),
                "sourceExpertId": item.get("sourceExpertId"),
                "proposedBy": item.get("proposedBy"),
                "affectedArtifactIds": list(item.get("affectedArtifactIds") or []),
                "createdAt": str(item.get("createdAt") or updated_at),
                "updatedAt": str(item.get("updatedAt") or updated_at),
                "confirmedBy": item.get("confirmedBy"),
                "confirmedAt": confirmed_at,
            }
        )
    return normalized


def _json_array(raw_json: str | None) -> list[dict[str, object]]:
    if not raw_json:
        return []
    loaded = json.loads(raw_json)
    return [item for item in loaded if isinstance(item, dict)] if isinstance(loaded, list) else []


def _backfill_artifact_dependency_index_v19(conn: sqlite3.Connection) -> None:
    now = _now()
    rows = conn.execute(
        """
        SELECT id, artifact_id, project_id, dependencies_json
        FROM artifact_versions
        """
    ).fetchall()
    for row in rows:
        version_id = str(row[0])
        artifact_id = str(row[1])
        project_id = str(row[2])
        for index, dependency in enumerate(_json_array(row[3])):
            upstream_artifact_id = dependency.get("artifactId") or dependency.get(
                "upstreamArtifactId"
            )
            if not upstream_artifact_id:
                continue
            dep_id = f"adep_{version_id}_{index}"
            conn.execute(
                """
                INSERT INTO artifact_dependencies (
                  id, project_id, artifact_id, artifact_version_id,
                  upstream_artifact_id, upstream_version_id, upstream_version,
                  relation, kind, label, status, required, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  upstream_artifact_id = excluded.upstream_artifact_id,
                  upstream_version_id = excluded.upstream_version_id,
                  upstream_version = excluded.upstream_version,
                  relation = excluded.relation,
                  kind = excluded.kind,
                  label = excluded.label,
                  status = excluded.status,
                  required = excluded.required
                """,
                (
                    dep_id,
                    project_id,
                    artifact_id,
                    version_id,
                    str(upstream_artifact_id),
                    dependency.get("versionId"),
                    dependency.get("version") or dependency.get("upstreamVersion"),
                    str(dependency.get("relation") or "requires"),
                    str(dependency.get("kind") or ""),
                    str(dependency.get("label") or upstream_artifact_id),
                    str(dependency.get("status") or ""),
                    1 if dependency.get("required", True) else 0,
                    now,
                ),
            )


def _backfill_project_workspaces(conn: sqlite3.Connection) -> None:
    now = _now()
    project_rows = conn.execute(
        "SELECT id, initial_idea FROM projects"
    ).fetchall()
    for project_id, initial_idea in project_rows:
        shared_context_id = _ensure_shared_context(conn, project_id, initial_idea, now)
        coordinator_id = _ensure_coordinator(conn, project_id, now)
        existing_conversation = conn.execute(
            """
            SELECT id FROM conversations
            WHERE project_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        problem_guide = _ensure_project_expert(
            conn,
            project_id=project_id,
            expert_type="problem_guide",
            conversation_id=existing_conversation[0] if existing_conversation else None,
            current_task="梳理问题、需求、项目方案和教学目标",
            now=now,
        )
        for expert_type in _infer_legacy_experts(conn, project_id):
            if expert_type == "problem_guide":
                continue
            _ensure_project_expert(
                conn,
                project_id=project_id,
                expert_type=expert_type,
                conversation_id=None,
                current_task=_default_task_for_expert(expert_type),
                now=now,
            )
        conn.execute(
            """
            UPDATE projects
            SET active_expert_id = COALESCE(active_expert_id, ?)
            WHERE id = ?
            """,
            (problem_guide, project_id),
        )
        _backfill_artifact_owners(conn, project_id, shared_context_id)
        _ = coordinator_id


def _ensure_shared_context(
    conn: sqlite3.Connection,
    project_id: str,
    initial_idea: str,
    now: str,
) -> str:
    row = conn.execute(
        "SELECT id FROM project_shared_contexts WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row:
        return str(row[0])
    context_id = _id("shared")
    goals = []
    if initial_idea.strip():
        goals.append(
            {
                "id": _id("fact"),
                "projectId": project_id,
                "field": "initialIdea",
                "key": "initialIdea",
                "value": initial_idea.strip(),
                "status": "proposed",
                "sourceType": "user",
                "sourceId": None,
                "sourceExpertId": None,
                "proposedBy": None,
                "confirmed": False,
                "confirmedBy": None,
                "confirmedAt": None,
                "supersededBy": None,
                "affectsArtifactIds": [],
                "createdAt": now,
                "updatedAt": now,
            }
        )
    conn.execute(
        """
        INSERT INTO project_shared_contexts (
          id, project_id, revision, goals_json, constraints_json, requirements_json,
          decisions_json, active_artifact_versions_json, updated_at
        ) VALUES (?, ?, 1, ?, '[]', '[]', '[]', '[]', ?)
        """,
        (context_id, project_id, json.dumps(goals, ensure_ascii=False), now),
    )
    return context_id


def _ensure_coordinator(
    conn: sqlite3.Connection,
    project_id: str,
    now: str,
) -> str:
    row = conn.execute(
        "SELECT id FROM project_coordinator_states WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row:
        return str(row[0])
    coordinator_id = _id("coord")
    current_item = {
        "id": _id("item"),
        "title": "继续完善项目需求",
        "description": "先在问题引导师对话中补齐目标、场景和关键约束。",
        "targetExpertId": None,
        "targetArtifactId": None,
        "actionLabel": "进入问题引导师",
        "severity": "info",
    }
    conn.execute(
        """
        INSERT INTO project_coordinator_states (
          id, project_id, current_item_json, conflicts_json, dependencies_json,
          updated_at
        ) VALUES (?, ?, ?, '[]', '[]', ?)
        """,
        (coordinator_id, project_id, json.dumps(current_item, ensure_ascii=False), now),
    )
    return coordinator_id


def _ensure_project_expert(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    expert_type: str,
    conversation_id: str | None,
    current_task: str,
    now: str,
) -> str:
    columns = _table_columns(conn, "project_experts")
    archived_filter = (
        "AND archived_legacy_thread = 0"
        if "archived_legacy_thread" in columns
        else ""
    )
    row = conn.execute(
        f"""
        SELECT id FROM project_experts
        WHERE project_id = ?
          AND expert_type = ?
          AND removed_at IS NULL
          {archived_filter}
        """,
        (project_id, expert_type),
    ).fetchone()
    if row:
        return str(row[0])
    definition = conn.execute(
        "SELECT id FROM expert_definitions WHERE expert_type = ?",
        (expert_type,),
    ).fetchone()
    if definition is None:
        raise RuntimeError(f"Missing expert definition: {expert_type}")
    if conversation_id is None:
        conversation_id = _id("conv")
        conn.execute(
            """
            INSERT INTO conversations (id, project_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, project_id, now, now),
        )
    expert_id = _id("pexp")
    memory_id = _id("pmem")
    status = "waiting_user" if expert_type == "problem_guide" else "idle"
    conn.execute(
        """
        INSERT INTO project_experts (
          id, project_id, expert_definition_id, expert_type, conversation_id,
          private_memory_id, status, current_task, added_at, removed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            expert_id,
            project_id,
            str(definition[0]),
            expert_type,
            conversation_id,
            memory_id,
            status,
            current_task,
            now,
        ),
    )
    if "workspace_status" in columns:
        conn.execute(
            "UPDATE project_experts SET workspace_status = ? WHERE id = ?",
            (_workspace_status_for_project_status(status), expert_id),
        )
    conn.execute(
        """
        INSERT INTO expert_private_memories (
          id, project_id, project_expert_id, notes_json, updated_at
        ) VALUES (?, ?, ?, '[]', ?)
        """,
        (memory_id, project_id, expert_id, now),
    )
    conn.execute(
        """
        INSERT INTO expert_drafts (project_expert_id, project_id, content, updated_at)
        VALUES (?, ?, '', NULL)
        """,
        (expert_id, project_id),
    )
    return expert_id


def _infer_legacy_experts(conn: sqlite3.Connection, project_id: str) -> set[str]:
    expert_types = {"problem_guide"}
    rows = conn.execute(
        """
        SELECT source_agent_id FROM artifacts
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    source_agents = {str(row[0]) for row in rows}
    if source_agents & {"spec-agent", "code-agent", "deploy-agent"}:
        expert_types.add("smart_engineer")
    if "cad-agent" in source_agents:
        expert_types.add("structure_engineer")
    return expert_types


def _backfill_artifact_owners(
    conn: sqlite3.Connection,
    project_id: str,
    shared_context_id: str,
) -> None:
    _ = shared_context_id
    expert_rows = conn.execute(
        "SELECT id, expert_type, conversation_id FROM project_experts WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    experts = {str(row[1]): (str(row[0]), str(row[2])) for row in expert_rows}
    artifact_rows = conn.execute(
        "SELECT id, source_agent_id FROM artifacts WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    for artifact_id, source_agent_id in artifact_rows:
        owner_type = _owner_type_for_source_agent(str(source_agent_id))
        owner = experts.get(owner_type) or experts.get("problem_guide")
        if owner is None:
            continue
        conn.execute(
            """
            UPDATE artifacts
            SET owner_expert_id = COALESCE(owner_expert_id, ?),
                owner_expert_type = COALESCE(owner_expert_type, ?),
                source_conversation_id = COALESCE(source_conversation_id, ?),
                shared_context_revision = COALESCE(shared_context_revision, 1)
            WHERE id = ?
            """,
            (owner[0], owner_type, owner[1], str(artifact_id)),
        )
        conn.execute(
            """
            UPDATE artifact_versions
            SET shared_context_revision = COALESCE(shared_context_revision, 1)
            WHERE artifact_id = ?
            """,
            (str(artifact_id),),
        )


def _owner_type_for_source_agent(source_agent_id: str) -> str:
    if source_agent_id in {"spec-agent", "code-agent", "deploy-agent"}:
        return "smart_engineer"
    if source_agent_id == "cad-agent":
        return "structure_engineer"
    return "problem_guide"


def _default_task_for_expert(expert_type: str) -> str:
    return {
        "problem_guide": "梳理问题、需求、项目方案和教学目标",
        "smart_engineer": "等待确认技术方案、硬件方案和 IO Map",
        "structure_engineer": "等待硬件尺寸、安装约束和结构目标",
    }.get(expert_type, "等待用户输入")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
