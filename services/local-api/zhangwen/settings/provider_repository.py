"""SQLite repository for the single versioned model-provider settings platform."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.domains.events.models import MODEL_SETTINGS_SCOPE_ID
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.llm.contracts import (
    LLMConfig,
    LLMModelId,
    LLMModelSelection,
    LLMProviderId,
    ModelConfig,
    SUPPORTED_MODELS,
    ThinkingMode,
)
from zhangwen.projects.repository import ProjectRepository
from zhangwen.security.credentials import credential_service_for_provider
from zhangwen.settings.models import (
    CloudContextScope,
    ModelRoutingProfile,
    ModelRoutingTarget,
    ModelWorkload,
    PrivacySettings,
    ProviderConfiguration,
    ProviderConnectionStatus,
    ProviderConnectionTestSummary,
    ProviderCredentialSummary,
    ProviderPreset,
    ProviderPresetId,
    RuntimeModelSelection,
    SaveModelRoutingRequest,
    SavePrivacySettingsRequest,
    validate_configuration_model,
    validate_routing_targets_are_distinct,
)


_DEFAULT_CONFIGURATION_ID = "provider_config_default"
_ROUTING_PROFILE_ID = "model_routing_profile_default"
_PRIVACY_SETTINGS_ID = "model_privacy_settings_default"


class ProviderSettingsError(ValueError):
    code = "PROVIDER_SETTINGS_ERROR"
    status_code = 422
    retryable = False


class ProviderConfigurationNotFoundError(ProviderSettingsError):
    code = "PROVIDER_CONFIGURATION_NOT_FOUND"
    status_code = 404


class ProviderSettingsConflictError(ProviderSettingsError):
    code = "PROVIDER_SETTINGS_CONFLICT"
    status_code = 409


@dataclass(frozen=True)
class CredentialLocator:
    state: str
    legacy_service: str | None


@dataclass(frozen=True)
class ResolvedRuntime:
    selection: RuntimeModelSelection
    config: LLMConfig


def provider_presets() -> list[ProviderPreset]:
    return [
        _preset(
            ProviderPresetId.DEEPSEEK,
            "DeepSeek",
            LLMProviderId.DEEPSEEK,
            "https://api.deepseek.com",
        ),
        _preset(
            ProviderPresetId.QWEN_OPENAI_COMPATIBLE,
            "千问（Qwen）",
            LLMProviderId.QWEN,
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        _preset(
            ProviderPresetId.GLM,
            "智谱 GLM",
            LLMProviderId.GLM,
            "https://open.bigmodel.cn/api/paas/v4",
        ),
        _preset(
            ProviderPresetId.KIMI,
            "Kimi",
            LLMProviderId.KIMI,
            "https://api.moonshot.cn/v1",
        ),
        ProviderPreset(
            id=ProviderPresetId.CUSTOM_OPENAI_COMPATIBLE,
            displayName="自定义 OpenAI-compatible",
            provider=LLMProviderId.OPENAI_COMPATIBLE,
            catalogRevision=1,
            defaultBaseUrl=None,
            defaultModels=[],
            customBaseUrl=True,
        ),
    ]


def provider_preset(preset_id: ProviderPresetId) -> ProviderPreset:
    for item in provider_presets():
        if item.id == preset_id:
            return item
    raise ProviderConfigurationNotFoundError("模型服务预设不存在。")


class ProviderSettingsRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._db_path = ProjectRepository(self._data_dir).db_path
        self._legacy_path = self._data_dir / "config" / "llm.json"
        self._events = RealtimeEventStore(self._db_path)
        self._ensure_seeded()

    @classmethod
    def from_db_path(cls, db_path: Path) -> "ProviderSettingsRepository":
        instance = cls.__new__(cls)
        instance._db_path = Path(db_path)
        instance._data_dir = instance._db_path.parent.parent
        instance._legacy_path = instance._data_dir / "config" / "llm.json"
        instance._events = RealtimeEventStore(instance._db_path)
        instance._ensure_seeded()
        return instance

    @property
    def db_path(self) -> Path:
        return self._db_path

    def list_configurations(self) -> list[ProviderConfiguration]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM provider_configurations
                WHERE deleted_at IS NULL
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
            return [self._configuration(conn, str(row["id"])) for row in rows]

    def get_configuration(self, configuration_id: str) -> ProviderConfiguration:
        with self._connect() as conn:
            return self._configuration(conn, configuration_id)

    def get_configuration_revision(
        self,
        configuration_revision_id: str,
    ) -> ProviderConfiguration:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT configuration_id FROM provider_configuration_revisions
                WHERE id = ?
                """,
                (configuration_revision_id,),
            ).fetchone()
            if row is None:
                raise ProviderConfigurationNotFoundError(
                    "模型服务配置版本不存在。"
                )
            return self._configuration(
                conn,
                str(row["configuration_id"]),
                revision_id=configuration_revision_id,
            )

    def create_configuration(
        self,
        *,
        preset_id: ProviderPresetId,
        name: str,
        provider: LLMProviderId,
        base_url: str,
        default_model: LLMModelSelection,
        custom_models: list[ModelConfig],
        thinking_mode: ThinkingMode,
        reasoning_effort: str | None,
        timeout_seconds: int,
        allow_private_network: bool,
    ) -> ProviderConfiguration:
        validate_configuration_model(
            provider=provider,
            default_model=str(default_model),
            custom_models=custom_models,
        )
        configuration_id = _id("provider_config")
        revision_id = _id("provider_config_revision")
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO provider_configurations (
                  id, preset_id, name, current_revision_id, enabled,
                  credential_state, legacy_credential_service, deleted_at,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 'CLEARED', NULL, NULL, ?, ?)
                """,
                (configuration_id, preset_id.value, name.strip(), revision_id, now, now),
            )
            self._insert_configuration_revision(
                conn,
                revision_id=revision_id,
                configuration_id=configuration_id,
                revision=1,
                provider=provider,
                base_url=base_url,
                default_model=default_model,
                custom_models=custom_models,
                thinking_mode=thinking_mode,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
                allow_private_network=allow_private_network,
                supersedes_revision_id=None,
                created_at=now,
            )
            created = self._configuration(conn, configuration_id)
            self._append_settings_event(
                conn,
                revision=created.revision,
                event_type="system.model-provider.configuration.changed",
                source_event_id=f"model-provider:{created.revision_id}:created",
                payload={
                    "configurationId": created.id,
                    "provider": created.provider.value,
                    "revisionId": created.revision_id,
                    "revision": created.revision,
                    "enabled": created.enabled,
                    "changeKind": "CREATED",
                },
            )
            return created

    def update_configuration(
        self,
        configuration_id: str,
        *,
        expected_revision: int,
        name: str,
        base_url: str,
        default_model: LLMModelSelection,
        custom_models: list[ModelConfig],
        thinking_mode: ThinkingMode,
        reasoning_effort: str | None,
        timeout_seconds: int,
        allow_private_network: bool,
        enabled: bool,
    ) -> ProviderConfiguration:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self._configuration(conn, configuration_id)
            if current.revision != expected_revision:
                raise ProviderSettingsConflictError(
                    "模型服务配置已更新，请刷新后重试。"
                )
            validate_configuration_model(
                provider=current.provider,
                default_model=str(default_model),
                custom_models=custom_models,
            )
            revision_id = _id("provider_config_revision")
            self._insert_configuration_revision(
                conn,
                revision_id=revision_id,
                configuration_id=configuration_id,
                revision=current.revision + 1,
                provider=current.provider,
                base_url=base_url,
                default_model=default_model,
                custom_models=custom_models,
                thinking_mode=thinking_mode,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
                allow_private_network=allow_private_network,
                supersedes_revision_id=current.revision_id,
                created_at=now,
            )
            conn.execute(
                """
                UPDATE provider_configurations
                SET name = ?, current_revision_id = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (name.strip(), revision_id, 1 if enabled else 0, now, configuration_id),
            )
            updated = self._configuration(conn, configuration_id)
            self._append_settings_event(
                conn,
                revision=updated.revision,
                event_type="system.model-provider.configuration.changed",
                source_event_id=f"model-provider:{updated.revision_id}:updated",
                payload={
                    "configurationId": updated.id,
                    "provider": updated.provider.value,
                    "revisionId": updated.revision_id,
                    "revision": updated.revision,
                    "enabled": updated.enabled,
                    "changeKind": "UPDATED",
                },
            )
            return updated

    def delete_configuration(self, configuration_id: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self._configuration(conn, configuration_id)
            profile = self._routing_profile(conn)
            targets = [profile.default_target, *profile.workload_routes.values()]
            if profile.fallback_target is not None:
                targets.append(profile.fallback_target)
            if any(item.configuration_id == configuration_id for item in targets):
                raise ProviderSettingsConflictError(
                    "这个模型服务仍在模型分工中使用，请先调整路由。"
                )
            conn.execute(
                """
                UPDATE provider_configurations
                SET enabled = 0, deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, configuration_id),
            )
            self._append_settings_event(
                conn,
                revision=current.revision,
                event_type="system.model-provider.configuration.changed",
                source_event_id=f"model-provider:{configuration_id}:deleted:{now}",
                payload={
                    "configurationId": current.id,
                    "provider": current.provider.value,
                    "revisionId": current.revision_id,
                    "revision": current.revision,
                    "enabled": False,
                    "changeKind": "DELETED",
                },
            )

    def credential_locator(self, configuration_id: str) -> CredentialLocator:
        with self._connect() as conn:
            row = self._configuration_row(conn, configuration_id)
            return CredentialLocator(
                state=str(row["credential_state"]),
                legacy_service=row["legacy_credential_service"],
            )

    def mark_credential_configured(self, configuration_id: str) -> None:
        self._set_credential_state(configuration_id, "CONFIGURED")

    def mark_credential_cleared(self, configuration_id: str) -> None:
        self._set_credential_state(configuration_id, "CLEARED")

    def get_routing_profile(self) -> ModelRoutingProfile:
        with self._connect() as conn:
            return self._routing_profile(conn)

    def save_routing_profile(
        self,
        request: SaveModelRoutingRequest,
    ) -> ModelRoutingProfile:
        validate_routing_targets_are_distinct(request)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self._routing_profile(conn)
            if current.revision != request.expected_revision:
                raise ProviderSettingsConflictError(
                    "模型分工已更新，请刷新后重试。"
                )
            self._validate_target(conn, request.default_target)
            if request.fallback_target is not None:
                self._validate_target(conn, request.fallback_target)
            for target in request.workload_routes.values():
                self._validate_target(conn, target)
            revision_id = _id("model_routing_revision")
            conn.execute(
                """
                INSERT INTO model_routing_profile_revisions (
                  id, profile_id, revision, default_target_json,
                  fallback_target_json, workload_routes_json,
                  supersedes_revision_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    current.id,
                    current.revision + 1,
                    _dump_model(request.default_target),
                    (
                        _dump_model(request.fallback_target)
                        if request.fallback_target is not None
                        else None
                    ),
                    _dump(
                        {
                            workload.value: target.model_dump(
                                mode="json", by_alias=True
                            )
                            for workload, target in request.workload_routes.items()
                        }
                    ),
                    current.revision_id,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE model_routing_profiles
                SET current_revision_id = ?, updated_at = ? WHERE id = ?
                """,
                (revision_id, now, current.id),
            )
            updated = self._routing_profile(conn)
            default_configuration = self._configuration(
                conn,
                updated.default_target.configuration_id,
            )
            self._append_settings_event(
                conn,
                revision=updated.revision,
                event_type="system.model-routing.changed",
                source_event_id=f"model-routing:{updated.revision_id}",
                payload={
                    "revisionId": updated.revision_id,
                    "revision": updated.revision,
                    "defaultProvider": default_configuration.provider.value,
                    "defaultModel": str(updated.default_target.model),
                    "fallbackConfigured": updated.fallback_target is not None,
                    "workloadCount": len(updated.workload_routes),
                },
            )
            return updated

    def get_privacy_settings(self) -> PrivacySettings:
        with self._connect() as conn:
            return self._privacy_settings(conn)

    def save_privacy_settings(
        self,
        request: SavePrivacySettingsRequest,
    ) -> PrivacySettings:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self._privacy_settings(conn)
            if current.revision != request.expected_revision:
                raise ProviderSettingsConflictError(
                    "隐私设置已更新，请刷新后重试。"
                )
            revision_id = _id("model_privacy_revision")
            conn.execute(
                """
                INSERT INTO model_privacy_setting_revisions (
                  id, settings_id, revision, context_scope,
                  cloud_trace_enabled, allow_automatic_fallback,
                  supersedes_revision_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    current.id,
                    current.revision + 1,
                    request.context_scope.value,
                    1 if request.cloud_trace_enabled else 0,
                    1 if request.allow_automatic_fallback else 0,
                    current.revision_id,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE model_privacy_settings
                SET current_revision_id = ?, updated_at = ? WHERE id = ?
                """,
                (revision_id, now, current.id),
            )
            updated = self._privacy_settings(conn)
            self._append_settings_event(
                conn,
                revision=updated.revision,
                event_type="system.model-privacy.changed",
                source_event_id=f"model-privacy:{updated.revision_id}",
                payload={
                    "revisionId": updated.revision_id,
                    "revision": updated.revision,
                    "contextScope": updated.context_scope.value,
                    "cloudTraceEnabled": updated.cloud_trace_enabled,
                    "automaticFallbackEnabled": updated.allow_automatic_fallback,
                },
            )
            return updated

    def resolve_runtime(
        self,
        workload: ModelWorkload,
        *,
        fallback: bool = False,
        owner_kind: str | None = None,
        owner_id: str | None = None,
    ) -> ResolvedRuntime:
        with self._connect() as conn:
            if owner_kind is not None and owner_id is not None:
                pinned = conn.execute(
                    """
                    SELECT * FROM model_runtime_selections
                    WHERE owner_kind = ? AND owner_id = ? AND fallback = ?
                    """,
                    (owner_kind, owner_id, 1 if fallback else 0),
                ).fetchone()
                if pinned is not None:
                    return self._resolved_from_runtime_row(conn, pinned)

            profile = self._routing_profile(conn)
            privacy = self._privacy_settings(conn)
            if fallback:
                if not privacy.allow_automatic_fallback:
                    raise ProviderSettingsConflictError(
                        "隐私设置尚未允许自动切换备用模型服务。"
                    )
                if profile.fallback_target is None:
                    raise ProviderSettingsConflictError("尚未配置备用模型服务。")
                target = profile.fallback_target
            else:
                target = profile.workload_routes.get(workload, profile.default_target)

            configuration = self._configuration(conn, target.configuration_id)
            if not configuration.enabled:
                raise ProviderSettingsConflictError("所选模型服务当前未启用。")
            self._validate_target(conn, target)
            selection = RuntimeModelSelection(
                providerConfigurationId=configuration.id,
                providerConfigurationRevisionId=configuration.revision_id,
                routingProfileRevisionId=profile.revision_id,
                provider=configuration.provider,
                model=target.model,
                workload=workload,
                fallback=fallback,
            )
            config = self._runtime_config(configuration, target.model, profile.revision_id)
            if owner_kind is not None and owner_id is not None:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT OR IGNORE INTO model_runtime_selections (
                      id, owner_kind, owner_id, provider_configuration_id,
                      provider_configuration_revision_id,
                      routing_profile_revision_id, provider, model, workload,
                      fallback, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id("model_runtime_selection"),
                        owner_kind,
                        owner_id,
                        selection.provider_configuration_id,
                        selection.provider_configuration_revision_id,
                        selection.routing_profile_revision_id,
                        selection.provider.value,
                        str(selection.model),
                        selection.workload.value,
                        1 if fallback else 0,
                        _now(),
                    ),
                )
                stored = conn.execute(
                    """
                    SELECT * FROM model_runtime_selections
                    WHERE owner_kind = ? AND owner_id = ? AND fallback = ?
                    """,
                    (owner_kind, owner_id, 1 if fallback else 0),
                ).fetchone()
                assert stored is not None
                return self._resolved_from_runtime_row(conn, stored)
            return ResolvedRuntime(selection=selection, config=config)

    def start_connection_test(
        self,
        configuration_id: str,
        test_id: str,
    ) -> ProviderConnectionTestSummary:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            configuration = self._configuration(conn, configuration_id)
            existing = conn.execute(
                "SELECT * FROM provider_connection_tests WHERE id = ?",
                (test_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["configuration_id"]) != configuration_id:
                    raise ProviderSettingsConflictError(
                        "同一测试标识不能用于不同模型服务。"
                    )
                return self._test_summary(existing)
            conn.execute(
                """
                INSERT INTO provider_connection_tests (
                  id, configuration_id, configuration_revision_id, status,
                  latency_ms, message, error_code, created_at, completed_at
                ) VALUES (?, ?, ?, 'RUNNING', NULL, ?, NULL, ?, NULL)
                """,
                (
                    test_id,
                    configuration_id,
                    configuration.revision_id,
                    "正在进行最小连接测试。",
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM provider_connection_tests WHERE id = ?",
                (test_id,),
            ).fetchone()
            assert row is not None
            summary = self._test_summary(row)
            self._append_settings_event(
                conn,
                revision=configuration.revision,
                event_type="system.model-provider.test.changed",
                source_event_id=f"model-provider-test:{test_id}:running",
                payload={
                    "configurationId": configuration_id,
                    "testId": test_id,
                    "testedRevisionId": summary.tested_revision_id,
                    "status": summary.status.value,
                    "latencyMs": summary.latency_ms,
                    "errorCode": summary.error_code,
                },
            )
            return summary

    def finish_connection_test(
        self,
        test_id: str,
        *,
        status: ProviderConnectionStatus,
        message: str,
        latency_ms: int | None,
        error_code: str | None,
    ) -> ProviderConnectionTestSummary:
        if status not in {
            ProviderConnectionStatus.PASSED,
            ProviderConnectionStatus.FAILED,
            ProviderConnectionStatus.CANCELED,
        }:
            raise ValueError("connection test must finish in a terminal state")
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM provider_connection_tests WHERE id = ?",
                (test_id,),
            ).fetchone()
            if row is None:
                raise ProviderConfigurationNotFoundError("连接测试不存在。")
            if str(row["status"]) == ProviderConnectionStatus.RUNNING.value:
                conn.execute(
                    """
                    UPDATE provider_connection_tests
                    SET status = ?, latency_ms = ?, message = ?, error_code = ?,
                        completed_at = ?
                    WHERE id = ?
                    """,
                    (status.value, latency_ms, message[:500], error_code, now, test_id),
                )
            final = conn.execute(
                "SELECT * FROM provider_connection_tests WHERE id = ?",
                (test_id,),
            ).fetchone()
            assert final is not None
            summary = self._test_summary(final)
            configuration = self._configuration(
                conn,
                str(final["configuration_id"]),
                revision_id=str(final["configuration_revision_id"]),
            )
            self._append_settings_event(
                conn,
                revision=configuration.revision,
                event_type="system.model-provider.test.changed",
                source_event_id=f"model-provider-test:{test_id}:{summary.status.value.lower()}",
                payload={
                    "configurationId": configuration.id,
                    "testId": test_id,
                    "testedRevisionId": summary.tested_revision_id,
                    "status": summary.status.value,
                    "latencyMs": summary.latency_ms,
                    "errorCode": summary.error_code,
                },
            )
            return summary

    def cancel_connection_test(self, test_id: str) -> ProviderConnectionTestSummary:
        return self.finish_connection_test(
            test_id,
            status=ProviderConnectionStatus.CANCELED,
            message="连接测试已取消。",
            latency_ms=None,
            error_code="CANCELED",
        )

    def _ensure_seeded(self) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            config_row = conn.execute(
                """
                SELECT id FROM provider_configurations
                WHERE deleted_at IS NULL ORDER BY created_at ASC LIMIT 1
                """
            ).fetchone()
            if config_row is None:
                legacy = self._load_legacy_config()
                self._seed_configuration(conn, legacy)
            self._seed_routing(conn)
            self._seed_privacy(conn)

    def _seed_configuration(self, conn: sqlite3.Connection, legacy: LLMConfig) -> None:
        preset_id = _preset_for_provider(legacy.provider)
        revision_id = "provider_config_revision_default_1"
        now = _now()
        conn.execute(
            """
            INSERT INTO provider_configurations (
              id, preset_id, name, current_revision_id, enabled,
              credential_state, legacy_credential_service, deleted_at,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 'FALLBACK', ?, NULL, ?, ?)
            """,
            (
                _DEFAULT_CONFIGURATION_ID,
                preset_id.value,
                provider_preset(preset_id).display_name,
                revision_id,
                credential_service_for_provider(legacy.provider.value),
                now,
                now,
            ),
        )
        self._insert_configuration_revision(
            conn,
            revision_id=revision_id,
            configuration_id=_DEFAULT_CONFIGURATION_ID,
            revision=1,
            provider=legacy.provider,
            base_url=legacy.baseUrl,
            default_model=legacy.defaultModel,
            custom_models=legacy.customModels,
            thinking_mode=legacy.thinkingMode,
            reasoning_effort=legacy.reasoningEffort,
            timeout_seconds=legacy.timeoutSeconds,
            allow_private_network=False,
            supersedes_revision_id=None,
            created_at=now,
        )

    def _seed_routing(self, conn: sqlite3.Connection) -> None:
        if conn.execute(
            "SELECT 1 FROM model_routing_profiles WHERE id = ?",
            (_ROUTING_PROFILE_ID,),
        ).fetchone() is not None:
            return
        configuration = self._configuration(conn, _DEFAULT_CONFIGURATION_ID)
        revision_id = "model_routing_revision_default_1"
        now = _now()
        target = ModelRoutingTarget(
            configurationId=configuration.id,
            model=configuration.default_model,
        )
        workload_routes: dict[str, object] = {}
        if configuration.provider == LLMProviderId.DEEPSEEK:
            workload_routes[ModelWorkload.ENGINEERING.value] = ModelRoutingTarget(
                configurationId=configuration.id,
                model=LLMModelId.DEEPSEEK_V4_PRO,
            ).model_dump(mode="json", by_alias=True)
        conn.execute(
            """
            INSERT INTO model_routing_profiles (
              id, current_revision_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (_ROUTING_PROFILE_ID, revision_id, now, now),
        )
        conn.execute(
            """
            INSERT INTO model_routing_profile_revisions (
              id, profile_id, revision, default_target_json,
              fallback_target_json, workload_routes_json,
              supersedes_revision_id, created_at
            ) VALUES (?, ?, 1, ?, NULL, ?, NULL, ?)
            """,
            (
                revision_id,
                _ROUTING_PROFILE_ID,
                _dump_model(target),
                _dump(workload_routes),
                now,
            ),
        )

    def _seed_privacy(self, conn: sqlite3.Connection) -> None:
        if conn.execute(
            "SELECT 1 FROM model_privacy_settings WHERE id = ?",
            (_PRIVACY_SETTINGS_ID,),
        ).fetchone() is not None:
            return
        revision_id = "model_privacy_revision_default_1"
        now = _now()
        conn.execute(
            """
            INSERT INTO model_privacy_settings (
              id, current_revision_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (_PRIVACY_SETTINGS_ID, revision_id, now, now),
        )
        conn.execute(
            """
            INSERT INTO model_privacy_setting_revisions (
              id, settings_id, revision, context_scope,
              cloud_trace_enabled, allow_automatic_fallback,
              supersedes_revision_id, created_at
            ) VALUES (?, ?, 1, 'MINIMUM_NEEDED', 0, 0, NULL, ?)
            """,
            (revision_id, _PRIVACY_SETTINGS_ID, now),
        )

    def _load_legacy_config(self) -> LLMConfig:
        if not self._legacy_path.exists():
            return LLMConfig()
        try:
            payload = json.loads(self._legacy_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return LLMConfig()
            payload.pop("apiKey", None)
            payload.pop("keySaved", None)
            payload.pop("maskedApiKey", None)
            return LLMConfig(**payload)
        except (OSError, ValueError, json.JSONDecodeError):
            return LLMConfig()

    def _configuration(
        self,
        conn: sqlite3.Connection,
        configuration_id: str,
        *,
        revision_id: str | None = None,
    ) -> ProviderConfiguration:
        row = self._configuration_row(conn, configuration_id)
        selected_revision_id = revision_id or str(row["current_revision_id"])
        revision = conn.execute(
            """
            SELECT * FROM provider_configuration_revisions
            WHERE id = ? AND configuration_id = ?
            """,
            (selected_revision_id, configuration_id),
        ).fetchone()
        if revision is None:
            raise ProviderConfigurationNotFoundError(
                "模型服务配置版本不存在。"
            )
        test_row = conn.execute(
            """
            SELECT * FROM provider_connection_tests
            WHERE configuration_id = ?
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (configuration_id,),
        ).fetchone()
        return ProviderConfiguration(
            id=configuration_id,
            revisionId=str(revision["id"]),
            revision=int(revision["revision"]),
            presetId=str(row["preset_id"]),
            name=str(row["name"]),
            provider=str(revision["provider"]),
            baseUrl=str(revision["base_url"]),
            defaultModel=str(revision["default_model"]),
            customModels=json.loads(str(revision["custom_models_json"])),
            thinkingMode=str(revision["thinking_mode"]),
            reasoningEffort=revision["reasoning_effort"],
            timeoutSeconds=int(revision["timeout_seconds"]),
            allowPrivateNetwork=bool(revision["allow_private_network"]),
            enabled=bool(row["enabled"]) and row["deleted_at"] is None,
            credential=ProviderCredentialSummary(configured=False, lastFour=None),
            connectionTest=(self._test_summary(test_row) if test_row is not None else None),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _configuration_row(
        self,
        conn: sqlite3.Connection,
        configuration_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM provider_configurations
            WHERE id = ? AND deleted_at IS NULL
            """,
            (configuration_id,),
        ).fetchone()
        if row is None:
            raise ProviderConfigurationNotFoundError("模型服务配置不存在。")
        return row

    def _routing_profile(self, conn: sqlite3.Connection) -> ModelRoutingProfile:
        row = conn.execute(
            "SELECT * FROM model_routing_profiles WHERE id = ?",
            (_ROUTING_PROFILE_ID,),
        ).fetchone()
        if row is None:
            raise ProviderSettingsError("模型分工尚未初始化。")
        revision = conn.execute(
            "SELECT * FROM model_routing_profile_revisions WHERE id = ?",
            (row["current_revision_id"],),
        ).fetchone()
        if revision is None:
            raise ProviderSettingsError("模型分工版本不存在。")
        raw_routes = json.loads(str(revision["workload_routes_json"]))
        return ModelRoutingProfile(
            id=str(row["id"]),
            revisionId=str(revision["id"]),
            revision=int(revision["revision"]),
            defaultTarget=json.loads(str(revision["default_target_json"])),
            fallbackTarget=(
                json.loads(str(revision["fallback_target_json"]))
                if revision["fallback_target_json"] is not None
                else None
            ),
            workloadRoutes=raw_routes,
            updatedAt=str(row["updated_at"]),
        )

    def _privacy_settings(self, conn: sqlite3.Connection) -> PrivacySettings:
        row = conn.execute(
            "SELECT * FROM model_privacy_settings WHERE id = ?",
            (_PRIVACY_SETTINGS_ID,),
        ).fetchone()
        if row is None:
            raise ProviderSettingsError("隐私设置尚未初始化。")
        revision = conn.execute(
            "SELECT * FROM model_privacy_setting_revisions WHERE id = ?",
            (row["current_revision_id"],),
        ).fetchone()
        if revision is None:
            raise ProviderSettingsError("隐私设置版本不存在。")
        return PrivacySettings(
            id=str(row["id"]),
            revisionId=str(revision["id"]),
            revision=int(revision["revision"]),
            contextScope=str(revision["context_scope"]),
            cloudTraceEnabled=bool(revision["cloud_trace_enabled"]),
            allowAutomaticFallback=bool(revision["allow_automatic_fallback"]),
            updatedAt=str(row["updated_at"]),
        )

    def _validate_target(
        self,
        conn: sqlite3.Connection,
        target: ModelRoutingTarget,
    ) -> None:
        configuration = self._configuration(conn, target.configuration_id)
        if not configuration.enabled:
            raise ProviderSettingsConflictError("模型分工不能使用已停用的服务。")
        validate_configuration_model(
            provider=configuration.provider,
            default_model=str(target.model),
            custom_models=configuration.custom_models,
        )

    def _resolved_from_runtime_row(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> ResolvedRuntime:
        configuration = self._configuration(
            conn,
            str(row["provider_configuration_id"]),
            revision_id=str(row["provider_configuration_revision_id"]),
        )
        selection = RuntimeModelSelection(
            providerConfigurationId=str(row["provider_configuration_id"]),
            providerConfigurationRevisionId=str(
                row["provider_configuration_revision_id"]
            ),
            routingProfileRevisionId=str(row["routing_profile_revision_id"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            workload=str(row["workload"]),
            fallback=bool(row["fallback"]),
        )
        return ResolvedRuntime(
            selection=selection,
            config=self._runtime_config(
                configuration,
                selection.model,
                selection.routing_profile_revision_id,
            ),
        )

    @staticmethod
    def _runtime_config(
        configuration: ProviderConfiguration,
        model: LLMModelSelection,
        routing_profile_revision_id: str,
    ) -> LLMConfig:
        return LLMConfig(
            provider=configuration.provider,
            baseUrl=configuration.base_url,
            defaultModel=model,
            customModels=configuration.custom_models,
            thinkingMode=configuration.thinking_mode,
            reasoningEffort=configuration.reasoning_effort,
            timeoutSeconds=configuration.timeout_seconds,
            keySaved=configuration.credential.configured,
            providerConfigurationId=configuration.id,
            providerConfigurationRevisionId=configuration.revision_id,
            routingProfileRevisionId=routing_profile_revision_id,
            updatedAt=configuration.updated_at,
        )

    @staticmethod
    def _insert_configuration_revision(
        conn: sqlite3.Connection,
        *,
        revision_id: str,
        configuration_id: str,
        revision: int,
        provider: LLMProviderId,
        base_url: str,
        default_model: LLMModelSelection,
        custom_models: list[ModelConfig],
        thinking_mode: ThinkingMode,
        reasoning_effort: str | None,
        timeout_seconds: int,
        allow_private_network: bool,
        supersedes_revision_id: str | None,
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO provider_configuration_revisions (
              id, configuration_id, revision, provider, base_url,
              default_model, custom_models_json, thinking_mode,
              reasoning_effort, timeout_seconds, allow_private_network,
              supersedes_revision_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision_id,
                configuration_id,
                revision,
                provider.value,
                base_url.rstrip("/"),
                str(default_model),
                _dump(
                    [
                        item.model_dump(mode="json", by_alias=True)
                        for item in custom_models
                    ]
                ),
                thinking_mode.value,
                reasoning_effort,
                timeout_seconds,
                1 if allow_private_network else 0,
                supersedes_revision_id,
                created_at,
            ),
        )

    def _set_credential_state(self, configuration_id: str, state: str) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            configuration = self._configuration(conn, configuration_id)
            changed_at = _now()
            conn.execute(
                """
                UPDATE provider_configurations
                SET credential_state = ?, updated_at = ? WHERE id = ?
                """,
                (state, changed_at, configuration_id),
            )
            self._append_settings_event(
                conn,
                revision=configuration.revision,
                event_type="system.model-provider.credential.changed",
                source_event_id=(
                    f"model-provider-credential:{configuration_id}:{state}:{changed_at}"
                ),
                payload={
                    "configurationId": configuration_id,
                    "providerConfigurationRevisionId": configuration.revision_id,
                    "configured": state == "CONFIGURED",
                },
            )

    def _append_settings_event(
        self,
        conn: sqlite3.Connection,
        *,
        revision: int,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> None:
        self._events.append_system_event(
            conn,
            system_id=MODEL_SETTINGS_SCOPE_ID,
            system_revision=revision,
            event_type=event_type,
            source_event_id=source_event_id,
            payload=payload,
        )

    @staticmethod
    def _test_summary(row: sqlite3.Row) -> ProviderConnectionTestSummary:
        status = ProviderConnectionStatus(str(row["status"]))
        return ProviderConnectionTestSummary(
            id=str(row["id"]),
            status=status,
            testedRevisionId=str(row["configuration_revision_id"]),
            testedAt=(
                str(row["completed_at"])
                if row["completed_at"] is not None
                else None
            ),
            latencyMs=(
                int(row["latency_ms"])
                if row["latency_ms"] is not None
                else None
            ),
            message=str(row["message"]),
            errorCode=(
                str(row["error_code"])
                if row["error_code"] is not None
                else None
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _preset(
    preset_id: ProviderPresetId,
    display_name: str,
    provider: LLMProviderId,
    default_base_url: str,
) -> ProviderPreset:
    return ProviderPreset(
        id=preset_id,
        displayName=display_name,
        provider=provider,
        catalogRevision=1,
        defaultBaseUrl=default_base_url,
        defaultModels=[item for item in SUPPORTED_MODELS if item.provider == provider],
        customBaseUrl=True,
    )


def _preset_for_provider(provider: LLMProviderId) -> ProviderPresetId:
    return {
        LLMProviderId.DEEPSEEK: ProviderPresetId.DEEPSEEK,
        LLMProviderId.QWEN: ProviderPresetId.QWEN_OPENAI_COMPATIBLE,
        LLMProviderId.GLM: ProviderPresetId.GLM,
        LLMProviderId.KIMI: ProviderPresetId.KIMI,
        LLMProviderId.OPENAI_COMPATIBLE: ProviderPresetId.CUSTOM_OPENAI_COMPATIBLE,
    }[provider]


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dump_model(value: object) -> str:
    if hasattr(value, "model_dump"):
        return _dump(value.model_dump(mode="json", by_alias=True))
    return _dump(value)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
