"""Web controller policy and extra packages over the original Hardware Skill store.

Preserves copied V1 files and never exposes unrelated archived controllers.
"""
from pathlib import Path

from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.models import HardwareCategory, HardwareSkillStatus, HardwareSkillSummary


WEB_CONTROLLERS = frozenset({
    "hw_seed_unihiker_k10", "hw_seeed_xiao_esp32s3_sense",
    "hw_labplus_mpython_esp32s3_v3", "hw_labplus_mpython_v2", "hw_esp32_generic_c3",
})
RELEASE_CATALOG = Path(__file__).resolve().parents[4] / "resources/hardware-skills"


class WebHardwareRepository(HardwareSkillRepository):
    def install_release_catalog(self) -> None:
        if not RELEASE_CATALOG.is_dir():
            raise RuntimeError("随项目发布的硬件资料目录缺失，请重新下载完整项目。")
        # Original validator/writer/projection; existing user packages are retained.
        self.install_bundled_catalog(source_root=RELEASE_CATALOG)

    def install_web_boards(self) -> None:
        self.install_bundled_catalog(source_root=Path(__file__).with_name("board-skills"))

    def list_skills(self, *, include_archived: bool = False) -> list[HardwareSkillSummary]:
        if include_archived:
            return super().list_skills(include_archived=True)
        skills = {item.componentId: item for item in super().list_skills()}
        for item in super().list_skills(include_archived=True):
            if item.category == HardwareCategory.MCU and item.componentId in WEB_CONTROLLERS and item.status == HardwareSkillStatus.ACTIVE:
                skills[item.componentId] = item
        return sorted(skills.values(), key=lambda item: (item.category.value, item.displayName.casefold()))
