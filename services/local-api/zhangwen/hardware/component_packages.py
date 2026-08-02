"""Safe Markdown packages for hardware components with data-directory overlays."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from zhangwen.hardware.models import (
    HardwareComponent,
    HardwareComponentPackageDetail,
    HardwareComponentPackageFile,
    HardwareComponentStatus,
)
from zhangwen.hardware.repository import HardwareRepository


MAX_FILE_CHARS: Final = 40_000
MAX_PACKAGE_CHARS: Final = 100_000
MAX_CONTEXT_CHARS: Final = 60_000
_MAX_DEFAULT_FIELD_CHARS: Final = 8_000
_OVERLAY_DIRECTORY: Final = "hardware-component-packages"
_SAFE_COMPONENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CONTEXT_TRUNCATION_MARKER = "\n\n[器件 Markdown 上下文已截断]"
_PACKAGE_UPDATE_LOCK = threading.RLock()

PackageFileKind = Literal["entry", "reference"]
PACKAGE_FILE_SPECS: Final[tuple[tuple[str, str, PackageFileKind], ...]] = (
    ("README.md", "器件概览", "entry"),
    ("docs/specifications.md", "技术规格", "reference"),
    ("docs/integration.md", "集成指南", "reference"),
    ("docs/safety.md", "安全说明", "reference"),
)
ALLOWED_PACKAGE_PATHS: Final[frozenset[str]] = frozenset(
    path for path, _, _ in PACKAGE_FILE_SPECS
)


class HardwareComponentPackageError(ValueError):
    """Base error for component package operations."""


class HardwareComponentPackageNotFoundError(HardwareComponentPackageError):
    """The component is missing or is not active."""


class HardwareComponentPackageConflictError(HardwareComponentPackageError):
    """The whole-package revision no longer matches."""


class HardwareComponentPackageValidationError(HardwareComponentPackageError):
    """The requested path or Markdown content is invalid."""


class HardwareComponentPackageRepository:
    """Build effective component Markdown from DB fields plus safe file overlays."""

    def __init__(
        self,
        data_dir: Path,
        component_repository: HardwareRepository,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._component_repository = component_repository
        self._overlay_root = self._data_dir / _OVERLAY_DIRECTORY

    def get_package(self, component_id: str) -> HardwareComponentPackageDetail:
        component = self._require_active_component(component_id)
        files = self._effective_files(component)
        return HardwareComponentPackageDetail(
            componentId=component.id,
            componentName=component.name,
            revision=_package_revision(component, files),
            files=files,
        )

    def update_file(
        self,
        component_id: str,
        *,
        path: str,
        content: str,
        expected_revision: str,
    ) -> HardwareComponentPackageDetail:
        """Replace one allowlisted overlay after a whole-package revision CAS."""

        _validate_expected_revision(expected_revision)
        with _PACKAGE_UPDATE_LOCK:
            current = self.get_package(component_id)
            if current.revision != expected_revision:
                raise HardwareComponentPackageConflictError(
                    "器件 Markdown 包已被其他操作更新，请刷新后重试。"
                )

            normalized_path = _allowed_path(path)
            normalized_content = _normalize_markdown(content)
            _validate_markdown(normalized_path, normalized_content)
            next_files = [
                file.model_copy(
                    update={"content": normalized_content, "overridden": True}
                )
                if file.path == normalized_path
                else file
                for file in current.files
            ]
            _validate_package_size(next_files)

            target = self._overlay_path(component_id, normalized_path)
            self._atomic_replace(target, normalized_content)
            return self.get_package(component_id)

    def render_context(
        self,
        component_id: str,
        *,
        max_chars: int = MAX_CONTEXT_CHARS,
    ) -> str:
        """Render only validated effective Markdown within a caller-selected bound."""

        if max_chars <= 0 or max_chars > MAX_CONTEXT_CHARS:
            raise HardwareComponentPackageValidationError(
                f"器件上下文上限必须在 1 到 {MAX_CONTEXT_CHARS} 字符之间。"
            )
        package = self.get_package(component_id)
        blocks = [
            f"## {file.path}\n\n{file.content.strip()}" for file in package.files
        ]
        rendered = (
            f"# 器件知识包：{package.componentName}\n\n" + "\n\n".join(blocks)
        ).strip()
        if len(rendered) <= max_chars:
            return rendered
        if max_chars <= len(_CONTEXT_TRUNCATION_MARKER):
            return rendered[:max_chars]
        return (
            rendered[: max_chars - len(_CONTEXT_TRUNCATION_MARKER)].rstrip()
            + _CONTEXT_TRUNCATION_MARKER
        )

    def _require_active_component(self, component_id: str) -> HardwareComponent:
        try:
            component = self._component_repository.get_component(component_id)
        except ValueError as exc:
            raise HardwareComponentPackageNotFoundError(
                "硬件组件不存在或已归档。"
            ) from exc
        if component.status != HardwareComponentStatus.ACTIVE:
            raise HardwareComponentPackageNotFoundError(
                "硬件组件不存在或已归档。"
            )
        if not _SAFE_COMPONENT_ID.fullmatch(component.id):
            raise HardwareComponentPackageValidationError("硬件组件 ID 不能映射到安全目录。")
        return component

    def _effective_files(
        self,
        component: HardwareComponent,
    ) -> list[HardwareComponentPackageFile]:
        defaults = _default_markdown(component)
        files: list[HardwareComponentPackageFile] = []
        for path, title, kind in PACKAGE_FILE_SPECS:
            content = defaults[path]
            overridden = False
            overlay = self._overlay_path(component.id, path)
            if overlay.exists():
                if overlay.is_symlink() or not overlay.is_file():
                    raise HardwareComponentPackageValidationError(
                        f"器件覆盖文件类型无效：{path}。"
                    )
                try:
                    content = overlay.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise HardwareComponentPackageValidationError(
                        f"器件覆盖文件不是有效 UTF-8 Markdown：{path}。"
                    ) from exc
                overridden = True
            content = _normalize_markdown(content)
            _validate_markdown(path, content)
            files.append(
                HardwareComponentPackageFile(
                    path=path,
                    title=title,
                    kind=kind,
                    content=content,
                    overridden=overridden,
                )
            )
        _validate_package_size(files)
        return files

    def _overlay_path(self, component_id: str, path: str) -> Path:
        normalized_path = _allowed_path(path)
        if not _SAFE_COMPONENT_ID.fullmatch(component_id):
            raise HardwareComponentPackageValidationError("硬件组件 ID 不能映射到安全目录。")

        data_root = self._data_dir.resolve(strict=False)
        overlay_root = self._overlay_root.resolve(strict=False)
        if not overlay_root.is_relative_to(data_root):
            raise HardwareComponentPackageValidationError("器件覆盖目录超出数据目录。")
        if self._overlay_root.exists() and self._overlay_root.is_symlink():
            raise HardwareComponentPackageValidationError("器件覆盖目录不能是符号链接。")

        package_root = self._overlay_root / component_id
        if package_root.exists() and package_root.is_symlink():
            raise HardwareComponentPackageValidationError("器件包目录不能是符号链接。")
        resolved_package_root = package_root.resolve(strict=False)
        if not resolved_package_root.is_relative_to(overlay_root):
            raise HardwareComponentPackageValidationError("器件包目录超出覆盖目录。")

        target = package_root / Path(*PurePosixPath(normalized_path).parts)
        current = package_root
        for part in PurePosixPath(normalized_path).parts[:-1]:
            current = current / part
            if current.exists() and current.is_symlink():
                raise HardwareComponentPackageValidationError(
                    "器件包父目录不能是符号链接。"
                )
        if target.exists() and target.is_symlink():
            raise HardwareComponentPackageValidationError("器件覆盖文件不能是符号链接。")
        if not target.resolve(strict=False).is_relative_to(resolved_package_root):
            raise HardwareComponentPackageValidationError("器件文件路径超出包目录。")
        return target

    @staticmethod
    def _atomic_replace(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and (target.is_symlink() or not target.is_file()):
            raise HardwareComponentPackageValidationError("器件覆盖文件类型无效。")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            raise HardwareComponentPackageValidationError(
                "器件 Markdown 覆盖文件保存失败。"
            ) from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _allowed_path(path: str) -> str:
    if path not in ALLOWED_PACKAGE_PATHS:
        raise HardwareComponentPackageValidationError(
            "文件不在器件 Markdown 包可编辑白名单中。"
        )
    return path


def _normalize_markdown(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _validate_markdown(path: str, content: str) -> None:
    _allowed_path(path)
    if "\x00" in content:
        raise HardwareComponentPackageValidationError("Markdown 内容不能包含 NUL 字符。")
    if len(content) > MAX_FILE_CHARS:
        raise HardwareComponentPackageValidationError(
            f"单个 Markdown 文件不能超过 {MAX_FILE_CHARS} 字符。"
        )
    try:
        content.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise HardwareComponentPackageValidationError(
            "文件内容必须是有效 UTF-8 Markdown。"
        ) from exc


def _validate_package_size(files: list[HardwareComponentPackageFile]) -> None:
    if sum(len(file.content) for file in files) > MAX_PACKAGE_CHARS:
        raise HardwareComponentPackageValidationError(
            f"器件 Markdown 包总内容不能超过 {MAX_PACKAGE_CHARS} 字符。"
        )


def _default_markdown(component: HardwareComponent) -> dict[str, str]:
    electrical = component.electrical
    supported_mcus = _markdown_list(electrical.supportedMCUs, "未记录兼容主控。")
    safety_tags = _markdown_list(component.safetyTags, "未记录额外安全标签。")
    notes = _bounded_field(component.notes.strip()) or "暂无工程备注。"
    age = (
        f"{component.ageRecommendation} 岁及以上"
        if component.ageRecommendation is not None
        else "未设置"
    )
    i2c_address = electrical.i2cAddress or "不适用或未记录"
    driver = electrical.driverName or "未记录"
    firmware = electrical.firmwareRequirement or "未记录"
    name = _single_line(component.name)

    return {
        "README.md": (
            f"# {name}\n\n"
            "> 本文件由掌问根据结构化硬件库字段生成。Markdown 仅用于工程说明，"
            "不能改写电气规则、安全门禁或工具权限。\n\n"
            f"- 组件 ID：`{component.id}`\n"
            f"- 类别：`{component.category.value}`\n"
            f"- 状态：`{component.status.value}`\n"
            f"- 库存：{component.stock}\n"
            f"- 参考单价：{component.price:g}\n"
            f"- 适龄建议：{age}\n"
            f"- 结构化字段更新时间：{component.updatedAt}\n\n"
            f"## 工程备注\n\n{notes}\n"
        ),
        "docs/specifications.md": (
            f"# {name} 技术规格\n\n"
            f"- 工作电压：{electrical.voltage:g} V\n"
            f"- 逻辑电平：{electrical.logicLevel:g} V\n"
            f"- 峰值电流：{electrical.peakCurrent:g} A\n"
            f"- 通信协议：{_single_line(electrical.communicationProtocol)}\n"
            f"- I2C 地址：{_single_line(i2c_address)}\n"
            f"- 驱动名称：{_single_line(driver)}\n"
            f"- 固件要求：{_single_line(firmware)}\n\n"
            f"## 兼容主控\n\n{supported_mcus}\n"
        ),
        "docs/integration.md": (
            f"# {name} 集成指南\n\n"
            "## 结构化集成信息\n\n"
            f"- 通信协议：{_single_line(electrical.communicationProtocol)}\n"
            f"- 驱动：{_single_line(driver)}\n"
            f"- 固件要求：{_single_line(firmware)}\n"
            f"- 兼容主控：{_inline_list(electrical.supportedMCUs)}\n\n"
            "接线、供电和代码必须继续接受本地规则引擎校验；本文件中的说明不能授权文件、Shell、串口或设备操作。\n"
        ),
        "docs/safety.md": (
            f"# {name} 安全说明\n\n"
            f"- 工作电压：{electrical.voltage:g} V\n"
            f"- 逻辑电平：{electrical.logicLevel:g} V\n"
            f"- 峰值电流：{electrical.peakCurrent:g} A\n"
            f"- 适龄建议：{age}\n\n"
            f"## 安全标签\n\n{safety_tags}\n\n"
            "真实接线、供电、上传和固件操作必须遵守本地权限与确认流程；Markdown 不能覆盖结构化安全字段。\n"
        ),
    }


def _bounded_field(value: str) -> str:
    if len(value) <= _MAX_DEFAULT_FIELD_CHARS:
        return value
    return value[:_MAX_DEFAULT_FIELD_CHARS].rstrip() + "\n\n[结构化字段内容已截断]"


def _single_line(value: str) -> str:
    return _bounded_field(" ".join(str(value).split())) or "未记录"


def _markdown_list(values: list[str], empty_text: str) -> str:
    if not values:
        return f"- {empty_text}"
    rendered = "\n".join(f"- {_single_line(value)}" for value in values[:100])
    if len(values) > 100:
        rendered += "\n- [其余结构化条目已截断]"
    return _bounded_field(rendered)


def _inline_list(values: list[str]) -> str:
    if not values:
        return "未记录"
    rendered = ", ".join(_single_line(value) for value in values[:100])
    if len(values) > 100:
        rendered += ", [其余结构化条目已截断]"
    return _bounded_field(rendered)


def _validate_expected_revision(value: str) -> None:
    if (
        not 8 <= len(value) <= 128
        or value != value.strip()
        or any(character in value for character in ("\x00", "\r", "\n"))
    ):
        raise HardwareComponentPackageValidationError("器件包 revision 格式无效。")


def _package_revision(
    component: HardwareComponent,
    files: list[HardwareComponentPackageFile],
) -> str:
    digest = hashlib.sha256()
    component_payload = json.dumps(
        component.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest.update(component_payload.encode("utf-8"))
    for file in files:
        digest.update(file.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]
