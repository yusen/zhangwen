"""Validated, read-only Board Skill packages for hardware-specific generation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator


BUNDLED_BOARD_SKILL_DIR = Path(__file__).resolve().parent / "board-skills"
_CHECKSUM_FILE = "CHECKSUMS.sha256"
_MANIFEST_FILE = "manifest.json"
_ENTRY_FILE = "SKILL.md"
_MAX_ENTRY_CHARS = 16_000
_MAX_REFERENCE_CHARS = 3_000
_MAX_TEMPLATE_CHARS = 3_000
_MAX_CONTEXT_CHARS = 24_000


class BoardSkillFileSpec(BaseModel):
    path: str
    size: int = Field(ge=0, le=1_000_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def _safe_path(cls, value: str) -> str:
        return _normalize_relative_path(value)


class BoardSkillManifest(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    version: str = Field(min_length=1, max_length=40)
    target: str = Field(min_length=1, max_length=120)
    runtime: Literal["MicroPython"]
    profile: str = Field(min_length=1, max_length=80)
    hardware_validation: bool
    syntax_validation: bool
    files: list[BoardSkillFileSpec] = Field(min_length=1, max_length=200)


class BoardSkillSummary(BaseModel):
    id: str
    name: str
    version: str
    profileId: str
    target: str
    runtime: Literal["MicroPython"] = "MicroPython"
    referenceCount: int
    templateCount: int
    exampleCount: int
    syntaxValidated: bool
    hardwareValidated: bool
    revision: str


class BoardSkillError(ValueError):
    pass


class BoardSkillNotFoundError(BoardSkillError):
    pass


class BoardSkillValidationError(BoardSkillError):
    pass


class BoardSkillPackage:
    def __init__(
        self,
        *,
        root: Path,
        manifest: BoardSkillManifest,
        summary: BoardSkillSummary,
        declared_paths: set[str],
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.summary = summary
        self.declared_paths = declared_paths

    def read_text(self, relative_path: str, *, max_chars: int) -> str:
        normalized = _normalize_relative_path(relative_path)
        if normalized not in self.declared_paths:
            raise BoardSkillValidationError("Board Skill 文件未在清单中声明。")
        candidate = _checked_file(self.root, normalized)
        try:
            content = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise BoardSkillValidationError("Board Skill 文件必须是 UTF-8 文本。") from exc
        if len(content) > max_chars:
            raise BoardSkillValidationError("Board Skill 上下文文件超过允许上限。")
        return content


class BoardSkillRepository:
    def __init__(self, root: Path = BUNDLED_BOARD_SKILL_DIR) -> None:
        self._root = Path(root)

    def summary_for_profile(self, profile_id: str) -> BoardSkillSummary | None:
        package = self.package_for_profile(profile_id, required=False)
        return package.summary if package is not None else None

    def package_for_profile(
        self,
        profile_id: str,
        *,
        required: bool = True,
    ) -> BoardSkillPackage | None:
        normalized_profile = _normalize_profile_id(profile_id)
        package_root = self._root / normalized_profile
        if not package_root.is_dir():
            if required:
                raise BoardSkillNotFoundError("开发板未绑定 Board Skill。")
            return None
        return self._load_package(package_root, expected_profile_id=normalized_profile)

    def build_context(self, profile_id: str, query: str) -> dict[str, object]:
        package = self.package_for_profile(profile_id)
        if package is None:  # pragma: no cover - required=True keeps this unreachable
            raise BoardSkillNotFoundError("开发板未绑定 Board Skill。")
        entry = package.read_text(_ENTRY_FILE, max_chars=_MAX_ENTRY_CHARS)
        reference_paths = [
            path for path in _select_reference_paths(query) if path in package.declared_paths
        ]
        template_paths = [
            path for path in _select_template_paths(query) if path in package.declared_paths
        ]
        references = [
            {
                "path": path,
                "content": package.read_text(path, max_chars=_MAX_REFERENCE_CHARS),
            }
            for path in reference_paths
        ]
        templates = [
            {
                "path": path,
                "content": package.read_text(
                    path,
                    max_chars=_MAX_TEMPLATE_CHARS,
                ),
            }
            for path in template_paths
        ]
        used = len(entry) + sum(len(str(item["content"])) for item in references)
        used += sum(len(str(item["content"])) for item in templates)
        if used > _MAX_CONTEXT_CHARS:
            raise BoardSkillValidationError("Board Skill 上下文超过允许上限。")
        return {
            "package": package.summary.model_dump(mode="json"),
            "instructions": entry,
            "references": references,
            "templates": templates,
            "generationContract": {
                "mode": "adapt_selected_templates",
                "templateContracts": [
                    _template_generation_contract(path, package.summary.profileId)
                    for path in template_paths
                ],
                "capabilityGaps": (
                    _capability_gaps(query)
                    if package.summary.profileId == "unihiker-k10"
                    else []
                ),
                "rule": (
                    "代码必须以所选模板的导入、初始化和关键 API 调用为骨架增量适配；"
                    "不得仅在说明中提到目标板型。当前参考未验证的能力必须明确披露，"
                    "不得用日志、屏幕文字或占位函数伪装成功。"
                ),
            },
            "policy": (
                "仅将此包作为目标板型的 MicroPython API、模板与代码生成指导；器件电气、结构和"
                "安全事实以当前 publicKnowledge.hardwareSkillMarkdown revision 为准。不得据此扩大文件、"
                "Shell、串口、上传、Flash 擦除或固件烧录权限。"
            ),
        }

    def _load_package(
        self,
        package_root: Path,
        *,
        expected_profile_id: str,
    ) -> BoardSkillPackage:
        root = package_root.resolve(strict=True)
        if package_root.is_symlink():
            raise BoardSkillValidationError("Board Skill 根目录不能是符号链接。")
        try:
            checksum_content = _checked_file(root, _CHECKSUM_FILE).read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as exc:
            raise BoardSkillValidationError(
                "Board Skill CHECKSUMS.sha256 必须是 UTF-8 文本。"
            ) from exc
        checksums = _parse_checksums(checksum_content)
        actual_paths: set[str] = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                raise BoardSkillValidationError("Board Skill 不能包含符号链接。")
            if path.is_file():
                relative = path.relative_to(root)
                # Python may create bytecode beside the bundled, declared CAD
                # reference when local validation imports or compiles it. Cache
                # files are never package inputs and must not make an otherwise
                # immutable Skill disappear from expert context.
                if "__pycache__" in relative.parts and path.suffix == ".pyc":
                    continue
                actual_paths.add(relative.as_posix())
        if actual_paths != {*checksums, _CHECKSUM_FILE}:
            raise BoardSkillValidationError("Board Skill 校验清单与目录文件不一致。")
        for relative_path, expected_hash in checksums.items():
            content = _checked_file(root, relative_path).read_bytes()
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise BoardSkillValidationError("Board Skill 文件 SHA-256 校验失败。")

        manifest_bytes = _checked_file(root, _MANIFEST_FILE).read_bytes()
        try:
            manifest = BoardSkillManifest.model_validate_json(manifest_bytes)
        except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise BoardSkillValidationError("Board Skill manifest.json 无效。") from exc
        manifest_paths = [item.path for item in manifest.files]
        if len(set(manifest_paths)) != len(manifest_paths):
            raise BoardSkillValidationError("Board Skill manifest 存在重复路径。")
        expected_manifest_paths = actual_paths - {_CHECKSUM_FILE, _MANIFEST_FILE}
        if set(manifest_paths) != expected_manifest_paths:
            raise BoardSkillValidationError("Board Skill manifest 文件集合不完整。")
        for spec in manifest.files:
            content = _checked_file(root, spec.path).read_bytes()
            if len(content) != spec.size or hashlib.sha256(content).hexdigest() != spec.sha256:
                raise BoardSkillValidationError("Board Skill manifest 文件校验失败。")
        manifest_profile_id = _normalize_profile_id(manifest.profile.replace("_", "-"))
        if manifest_profile_id != expected_profile_id:
            raise BoardSkillValidationError("Board Skill 与 BoardProfile 绑定不一致。")
        if _ENTRY_FILE not in expected_manifest_paths:
            raise BoardSkillValidationError("Board Skill 缺少 SKILL.md。")

        reference_paths = {
            path for path in manifest_paths if path.startswith("references/") and path.endswith(".md")
        }
        template_paths = {
            path for path in manifest_paths if path.startswith("templates/") and path.endswith(".py")
        }
        example_names = {
            PurePosixPath(path).parts[1]
            for path in manifest_paths
            if path.startswith("examples/") and path.endswith("/main.py")
        }
        summary = BoardSkillSummary(
            id=manifest.name,
            name=manifest.name,
            version=manifest.version,
            profileId=manifest_profile_id,
            target=manifest.target,
            runtime=manifest.runtime,
            referenceCount=len(reference_paths),
            templateCount=len(template_paths),
            exampleCount=len(example_names),
            syntaxValidated=manifest.syntax_validation,
            hardwareValidated=manifest.hardware_validation,
            revision=hashlib.sha256(manifest_bytes).hexdigest()[:24],
        )
        return BoardSkillPackage(
            root=root,
            manifest=manifest,
            summary=summary,
            declared_paths=set(manifest_paths),
        )


_REFERENCE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "references/03-screen-api.md",
        ("屏幕", "显示", "绘图", "文字", "screen", "摄像头", "相机", "预览", "拍照", "照片"),
    ),
    (
        "references/04-onboard-api.md",
        ("按钮", "按键", "温湿度", "光线", "加速度", "麦克风", "rgb", "板载"),
    ),
    (
        "references/05-storage-audio-api.md",
        ("存储", "保存", "文件", "tf", "sd", "录音", "播放", "音频", "相册", "照片"),
    ),
    ("references/06-connectivity-api.md", ("wifi", "mqtt", "ble", "蓝牙", "联网", "网络")),
    ("references/07-ai-api.md", ("ai", "二维码", "识别", "运动检测", "语音", "人脸")),
    ("references/08-external-hardware-api.md", ("gpio", "舵机", "超声波", "外设", "传感器", "neopixel", "dht", "ds18b20")),
    ("references/09-safety-and-troubleshooting.md", ("安全", "故障", "报错", "排查", "异常")),
    ("references/10-verification-matrix.md", ("验证", "测试", "检查")),
    ("references/01-platform-and-firmware.md", ("平台", "固件版本", "micropython 版本")),
)

_TEMPLATE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("templates/01_screen_shapes.py", ("屏幕", "绘图", "图形", "screen")),
    ("templates/02_onboard_dashboard.py", ("仪表盘", "环境监测", "板载温湿度", "温湿度显示", "温湿度")),
    ("templates/03_button_event_safe.py", ("按钮", "按键")),
    ("templates/04_rgb_status.py", ("rgb", "状态灯")),
    ("templates/05_tf_card_list.py", ("tf", "sd", "存储卡", "保存到 tf", "照片保存", "保存照片", "相册")),
    ("templates/06_audio_record_play.py", ("录音", "播放", "音频")),
    ("templates/07_wifi_connect.py", ("wifi", "联网")),
    ("templates/08_mqtt_probe.py", ("mqtt",)),
    ("templates/09_ble_hid.py", ("ble", "蓝牙", "hid")),
    ("templates/10_ai_qr_scanner.py", ("二维码", "qr")),
    ("templates/11_ai_motion_detect.py", ("运动检测",)),
    ("templates/12_gpio_test.py", ("gpio",)),
    ("templates/13_servo_safe.py", ("舵机", "servo")),
    (
        "templates/14_camera_preview.py",
        ("摄像头拍照", "相机拍照", "摄像头", "相机", "预览", "拍照", "照片"),
    ),
    ("templates/15_asr_tts.py", ("语音", "asr", "tts")),
    ("templates/16_ai_face_recognition.py", ("人脸",)),
    ("templates/17_dht_sensor.py", ("dht", "dht11", "dht22", "外接温湿度")),
    ("templates/18_ds18b20_sensor.py", ("ds18b20",)),
    ("templates/19_ultrasonic.py", ("超声波", "测距")),
    ("templates/20_neopixel.py", ("neopixel", "灯带")),
    ("templates/21_force_sensor_probe.py", ("压力", "力传感器")),
)


_TEMPLATE_GENERATION_CONTRACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "templates/01_screen_shapes.py": {
        "requiredImports": ("unihiker_k10:screen",),
        "requiredCalls": ("screen.init", "screen.show_draw"),
        "oneOfCalls": (
            "screen.draw_line",
            "screen.draw_point",
            "screen.draw_rect",
            "screen.draw_circle",
            "screen.draw_text",
        ),
    },
    "templates/02_onboard_dashboard.py": {
        "requiredImports": ("unihiker_k10:screen",),
        "requiredCalls": ("screen.init", "screen.show_draw"),
        "oneOfCalls": (
            "temp_humi.read_temp",
            "temp_humi.read_humi",
            "light.read",
            "acce.read_x",
        ),
    },
    "templates/03_button_event_safe.py": {
        "requiredImports": ("unihiker_k10:button",),
        "requiredCalls": ("button",),
        "oneOfCalls": (),
    },
    "templates/04_rgb_status.py": {
        "requiredImports": ("unihiker_k10:rgb",),
        "requiredCalls": ("rgb.write",),
        "oneOfCalls": (),
    },
    "templates/05_tf_card_list.py": {
        "requiredImports": ("k10_base:TF_card",),
        "requiredCalls": ("TF_card", "os.listdir"),
        "oneOfCalls": (),
    },
    "templates/06_audio_record_play.py": {
        "requiredImports": (),
        "requiredCalls": (),
        "oneOfCalls": (
            "mic.recode_sys",
            "mic.recode_tf",
            "speaker.play_sys_music",
            "speaker.play_tf_music",
        ),
    },
    "templates/07_wifi_connect.py": {
        "requiredImports": ("k10_base:WiFi",),
        "requiredCalls": ("WiFi", "WiFi.connect"),
        "oneOfCalls": (),
    },
    "templates/08_mqtt_probe.py": {
        "requiredImports": ("k10_base:MqttClient",),
        "requiredCalls": ("MqttClient",),
        "oneOfCalls": (),
    },
    "templates/09_ble_hid.py": {
        "requiredImports": ("unihiker_k10:hid",),
        "requiredCalls": ("hid",),
        "oneOfCalls": ("hid.isconnected", "hid.keyboard_send"),
    },
    "templates/10_ai_qr_scanner.py": {
        "requiredImports": ("ai", "unihiker_k10:screen"),
        "requiredCalls": (
            "ai.init_ai",
            "ai.camera_start",
            "ai.code_scanner",
            "ai.camera_capture",
            "screen.show_camera_img",
            "ai.deinit_ai",
        ),
        "oneOfCalls": (),
    },
    "templates/11_ai_motion_detect.py": {
        "requiredImports": ("ai", "unihiker_k10:screen"),
        "requiredCalls": (
            "ai.init_ai",
            "ai.camera_start",
            "ai.move_detect",
            "ai.camera_capture",
            "screen.show_camera_img",
            "ai.deinit_ai",
        ),
        "oneOfCalls": (),
    },
    "templates/12_gpio_test.py": {
        "requiredImports": ("unihiker_k10:pin",),
        "requiredCalls": ("pin",),
        "oneOfCalls": (),
    },
    "templates/13_servo_safe.py": {
        "requiredImports": ("unihiker_k10:servo",),
        "requiredCalls": ("servo", "servo.angle"),
        "oneOfCalls": (),
    },
    "templates/14_camera_preview.py": {
        "requiredImports": ("k10_base:Camera", "unihiker_k10:screen"),
        "requiredCalls": ("Camera", "Camera.init", "screen.init", "screen.show_camera"),
        "oneOfCalls": (),
    },
    "templates/15_asr_tts.py": {
        "requiredImports": ("asr",),
        "requiredCalls": ("asr.init_asr",),
        "oneOfCalls": ("asr.start_asr", "asr.start_tts"),
    },
    "templates/16_ai_face_recognition.py": {
        "requiredImports": ("ai", "unihiker_k10:screen"),
        "requiredCalls": (
            "ai.init_ai",
            "ai.camera_start",
            "ai.face_recognize_start",
            "ai.camera_capture",
            "screen.show_camera_img",
            "ai.deinit_ai",
        ),
        "oneOfCalls": (),
    },
    "templates/17_dht_sensor.py": {
        "requiredImports": ("unihiker_k10:dht",),
        "requiredCalls": ("dht", "dht.read"),
        "oneOfCalls": (),
    },
    "templates/18_ds18b20_sensor.py": {
        "requiredImports": ("unihiker_k10:ds18b20",),
        "requiredCalls": ("ds18b20", "ds18b20.read"),
        "oneOfCalls": (),
    },
    "templates/19_ultrasonic.py": {
        "requiredImports": ("unihiker_k10:ultrasonic",),
        "requiredCalls": ("ultrasonic", "ultrasonic.distance"),
        "oneOfCalls": (),
    },
    "templates/20_neopixel.py": {
        "requiredImports": ("unihiker_k10:neopixel",),
        "requiredCalls": ("neopixel", "neopixel.write"),
        "oneOfCalls": (),
    },
    "templates/21_force_sensor_probe.py": {
        "requiredImports": ("unihiker_k10:force",),
        "requiredCalls": ("force", "force.read"),
        "oneOfCalls": (),
    },
}


_CAPABILITY_GAP_RULES: tuple[tuple[tuple[str, ...], dict[str, object]], ...] = (
    (
        ("拍照", "保存照片", "照片保存", "take photo", "take picture"),
        {
            "id": "k10-camera-still-image-save",
            "status": "UNVERIFIED",
            "instruction": (
                "当前 K10 Skill 只证实 Camera 实时预览、AI 图像帧显示和 TF 卡访问，"
                "没有证实把 camera_capture 返回值编码并保存为静态照片。不得声称照片已拍摄或保存成功；"
                "可以交付以 Camera 模板为骨架的实时预览，并明确说明该能力边界。"
            ),
            "prohibitedSuccessClaims": (
                "照片已保存",
                "拍照完成",
                "拍照成功",
                "photo captured",
                "photo saved",
            ),
            "requiredDisclosureGroups": (
                ("未验证", "未证实", "没有证实", "待受信参考"),
                ("不声称", "只交付", "仅交付", "暂不"),
            ),
        },
    ),
    (
        ("电子相册", "照片浏览", "图片浏览"),
        {
            "id": "k10-photo-album-image-decode",
            "status": "UNVERIFIED",
            "instruction": (
                "当前 K10 Skill 只证实 TF 卡目录访问，没有证实从 TF 卡解码并显示任意照片文件。"
                "不得把文件列表或占位画面描述成电子相册已经完成。"
            ),
            "prohibitedSuccessClaims": ("电子相册已完成", "照片已显示", "图片已显示"),
            "requiredDisclosureGroups": (
                ("未验证", "未证实", "没有证实", "待受信参考"),
                ("不声称", "只交付", "仅交付", "暂不"),
            ),
        },
    ),
)


def _select_reference_paths(query: str) -> list[str]:
    normalized = query.lower()[:4_000]
    selected = ["references/00-sources-and-scope.md"]
    ranked = sorted(
        (
            (
                sum(len(keyword) * normalized.count(keyword) for keyword in keywords),
                path,
            )
            for path, keywords in _REFERENCE_RULES
        ),
        key=lambda item: (-item[0], item[1]),
    )
    matched = {path for score, path in ranked if score > 0}
    selected.extend(path for path, _ in _REFERENCE_RULES if path in matched)
    selected = selected[:4]
    return selected


def _select_template_paths(query: str) -> list[str]:
    normalized = query.lower()[:4_000]
    ranked = sorted(
        (
            (
                sum(len(keyword) * normalized.count(keyword) for keyword in keywords),
                path,
            )
            for path, keywords in _TEMPLATE_RULES
        ),
        key=lambda item: (-item[0], item[1]),
    )
    positive = [(score, path) for score, path in ranked if score > 0]
    if not positive:
        return ["templates/00_profile_probe.py"]
    top_score = positive[0][0]
    return [
        path
        for score, path in positive
        if score * 2 >= top_score
    ][:2]


def _template_generation_contract(
    path: str,
    profile_id: str = "unihiker-k10",
) -> dict[str, object]:
    if profile_id == "xiao-esp32s3-sense":
        xiao_contracts: dict[str, dict[str, tuple[str, ...]]] = {
            "templates/00_profile_probe.py": {
                "requiredImports": ("machine", "sys"),
            },
            "templates/12_gpio_test.py": {
                "requiredImports": ("machine:Pin",),
                "requiredCalls": ("Pin",),
            },
        }
        contract = xiao_contracts.get(path, {})
    else:
        contract = _TEMPLATE_GENERATION_CONTRACTS.get(path, {})
    return {
        "path": path,
        "requiredImports": list(contract.get("requiredImports", ())),
        "requiredCalls": list(contract.get("requiredCalls", ())),
        "oneOfCalls": list(contract.get("oneOfCalls", ())),
    }


def _capability_gaps(query: str) -> list[dict[str, object]]:
    normalized = query.casefold()[:4_000]
    return [
        {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in payload.items()
        }
        for triggers, payload in _CAPABILITY_GAP_RULES
        if any(trigger in normalized for trigger in triggers)
    ]


def _parse_checksums(content: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise BoardSkillValidationError("Board Skill CHECKSUMS.sha256 格式无效。")
        path = _normalize_relative_path(match.group(2))
        if path in checksums or path == _CHECKSUM_FILE:
            raise BoardSkillValidationError("Board Skill 校验清单存在重复或递归项。")
        checksums[path] = match.group(1)
    if _MANIFEST_FILE not in checksums or _ENTRY_FILE not in checksums:
        raise BoardSkillValidationError("Board Skill 校验清单缺少必需文件。")
    return checksums


def _checked_file(root: Path, relative_path: str) -> Path:
    normalized = _normalize_relative_path(relative_path)
    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise BoardSkillValidationError("Board Skill 文件不存在。") from exc
    if not resolved.is_relative_to(root) or candidate.is_symlink() or not candidate.is_file():
        raise BoardSkillValidationError("Board Skill 路径不是包内普通文件。")
    for parent in candidate.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise BoardSkillValidationError("Board Skill 目录不能包含符号链接。")
    return candidate


def _normalize_relative_path(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise BoardSkillValidationError("Board Skill 路径无效。")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BoardSkillValidationError("Board Skill 路径必须是安全相对路径。")
    return path.as_posix()


def _normalize_profile_id(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
        raise BoardSkillValidationError("Board Skill profile ID 无效。")
    return normalized
