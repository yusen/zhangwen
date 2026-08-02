"""Bounded validation for imported firmware application archives."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import struct
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse

from pydantic import ValidationError

from zhangwen.device_lab.boards import board_capability
from zhangwen.device_lab.models import FirmwareApplicationManifestV1


MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_FILES = 64
COMMON_NVS_RANGE = (0x9000, 0xF000)


class ApplicationValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedApplicationArchive:
    archive: bytes
    archive_sha256: str
    manifest: FirmwareApplicationManifestV1
    simulation_capability: str


def validate_application_archive(encoded: str) -> ValidatedApplicationArchive:
    try:
        archive = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_BASE64_INVALID",
            "应用包不是有效的 Base64 ZIP。",
        ) from exc
    if not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_ARCHIVE_SIZE_INVALID",
            "应用包必须大于 0 且不超过 64 MB。",
        )
    try:
        package = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_ZIP_INVALID", "应用包 ZIP 已损坏。"
        ) from exc
    with package:
        infos = [info for info in package.infolist() if not info.is_dir()]
        if not infos or len(infos) > MAX_ARCHIVE_FILES:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_FILE_COUNT_INVALID",
                "应用包文件数量超出允许范围。",
            )
        names: set[str] = set()
        expanded = 0
        for info in infos:
            name = _safe_member_name(info.filename)
            if name in names:
                raise ApplicationValidationError(
                    "FIRMWARE_APPLICATION_DUPLICATE_PATH", "应用包包含重复路径。"
                )
            names.add(name)
            expanded += info.file_size
            if info.flag_bits & 0x1:
                raise ApplicationValidationError(
                    "FIRMWARE_APPLICATION_ENCRYPTED", "不支持加密 ZIP 应用包。"
                )
            if info.file_size > 1024 * 1024 and info.file_size > max(info.compress_size, 1) * 200:
                raise ApplicationValidationError(
                    "FIRMWARE_APPLICATION_COMPRESSION_RATIO_INVALID",
                    "应用包包含异常压缩比文件。",
                )
        if expanded > MAX_EXPANDED_BYTES:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_EXPANDED_SIZE_INVALID",
                "应用包解压后不能超过 256 MB。",
            )
        if "manifest.json" not in names:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_MANIFEST_MISSING",
                "应用包根目录缺少 manifest.json。",
            )
        try:
            manifest_value = json.loads(package.read("manifest.json"))
            manifest = FirmwareApplicationManifestV1.model_validate(manifest_value)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_MANIFEST_INVALID",
                "应用 manifest 不符合 zhangwen.firmware-application/v1。",
            ) from exc
        _validate_manifest(package, names, manifest)
    capability = "FULL" if manifest.simulationImage is not None else (
        "UART_ONLY" if manifest.debugProtocolVersion is not None else "NONE"
    )
    return ValidatedApplicationArchive(
        archive=archive,
        archive_sha256=hashlib.sha256(archive).hexdigest(),
        manifest=manifest,
        simulation_capability=capability,
    )


def _safe_member_name(value: str) -> str:
    if "\\" in value or value.startswith(("/", "\\")):
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_PATH_INVALID", "应用包包含不安全路径。"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_PATH_INVALID", "应用包包含不安全路径。"
        )
    normalized = path.as_posix()
    if len(normalized) > 240:
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_PATH_INVALID", "应用包路径过长。"
        )
    return normalized


def _validate_manifest(
    package: zipfile.ZipFile,
    names: set[str],
    manifest: FirmwareApplicationManifestV1,
) -> None:
    board = board_capability(manifest.boardId)
    if manifest.flashSizeBytes != board.flashSizeBytes or manifest.psramSizeBytes != board.psramSizeBytes:
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_MEMORY_MISMATCH",
            "应用声明的 Flash/PSRAM 与所选板型不一致。",
        )
    if manifest.sourceUrl:
        parsed = urlparse(manifest.sourceUrl)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_SOURCE_URL_INVALID", "应用来源必须是 HTTPS 地址。"
            )
    ranges: list[tuple[int, int, str]] = []
    partition_table: bytes | None = None
    for segment in manifest.deviceImages:
        path = _safe_member_name(segment.path)
        if path not in names:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_IMAGE_MISSING", f"应用包缺少镜像 {path}。"
            )
        payload = package.read(path)
        _validate_asset(payload, segment.sizeBytes, segment.sha256, path)
        end = segment.address + segment.sizeBytes
        if end > board.flashSizeBytes:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_SEGMENT_OUT_OF_RANGE", "固件段超出板型 Flash 容量。"
            )
        for start, previous_end, _ in ranges:
            if segment.address < previous_end and end > start:
                raise ApplicationValidationError(
                    "FIRMWARE_APPLICATION_SEGMENT_OVERLAP", "固件段地址相互重叠。"
                )
        ranges.append((segment.address, end, segment.kind))
        if segment.kind == "partition-table":
            partition_table = payload
    protected = [COMMON_NVS_RANGE]
    if partition_table is not None:
        protected.extend(_protected_partition_ranges(partition_table))
    for start, end, kind in ranges:
        if kind == "partition-table":
            continue
        if any(start < protected_end and end > protected_start for protected_start, protected_end in protected):
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_PROTECTED_PARTITION",
                "应用镜像会覆盖 NVS 或用户数据分区，掌问已拒绝导入。",
            )
    if manifest.simulationImage is not None:
        image = manifest.simulationImage
        path = _safe_member_name(image.path)
        if path not in names:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_SIMULATION_IMAGE_MISSING",
                "应用包缺少仿真 Flash 镜像。",
            )
        payload = package.read(path)
        _validate_asset(payload, image.sizeBytes, image.sha256, path)
        if image.sizeBytes > board.flashSizeBytes:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_SIMULATION_IMAGE_SIZE_INVALID",
                "仿真 Flash 镜像超过板型容量。",
            )
    if manifest.elfImage is not None:
        image = manifest.elfImage
        path = _safe_member_name(image.path)
        if path not in names:
            raise ApplicationValidationError(
                "FIRMWARE_APPLICATION_ELF_IMAGE_MISSING",
                "应用包缺少声明的 ELF 调试镜像。",
            )
        _validate_asset(package.read(path), image.sizeBytes, image.sha256, path)


def _validate_asset(payload: bytes, size: int, expected_sha256: str, path: str) -> None:
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ApplicationValidationError(
            "FIRMWARE_APPLICATION_IMAGE_HASH_MISMATCH",
            f"镜像 {path} 的大小或 SHA-256 不一致。",
        )


def _protected_partition_ranges(payload: bytes) -> list[tuple[int, int]]:
    protected: list[tuple[int, int]] = []
    for offset in range(0, len(payload) - 31, 32):
        entry = payload[offset : offset + 32]
        magic, partition_type, subtype, start, size = struct.unpack_from("<HBBII", entry)
        if magic == 0xFFFF:
            break
        if magic != 0x50AA or size <= 0:
            continue
        label = entry[12:28].split(b"\0", 1)[0].decode("ascii", errors="ignore").casefold()
        is_persistent_data = partition_type == 1 and (
            subtype in {0x02, 0x81, 0x82, 0x83}
            or label in {"nvs", "storage", "data", "fat", "spiffs", "littlefs"}
        )
        if is_persistent_data:
            protected.append((start, start + size))
    return protected
