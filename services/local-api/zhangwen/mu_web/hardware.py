"""Web controller policy and extra packages over the original Hardware Skill store.

Preserves copied V1 files and never exposes unrelated archived controllers.
"""
import json
import re
from pathlib import Path

from zhangwen.hardware.hardware_skills import HardwareSkillRepository, HardwareSkillNotFoundError
from zhangwen.hardware.models import HardwareCategory, HardwareSkillStatus, HardwareSkillSummary, ValidationCheck, ValidationSeverity


WEB_CONTROLLERS = frozenset({
    "hw_seed_unihiker_k10", "hw_seeed_xiao_esp32s3_sense",
    "hw_labplus_mpython_esp32s3_v3", "hw_labplus_mpython_v2", "hw_esp32_generic_c3",
})
RELEASE_CATALOG = Path(__file__).resolve().parents[4] / "resources/hardware-skills"
VENDOR_CATALOG = RELEASE_CATALOG.parent / "vendor-hardware-skills"


def module_type(name: str, category: str) -> str:
    """Search labels only, never infer electrical parameters or drivers."""
    groups = (
        [(r'舵机|servo', '舵机'), (r'步进|stepper', '步进电机'), (r'泵|pump', '泵'),
         (r'继电器|relay', '继电器'), (r'语音|蜂鸣|mp3|speaker|buzzer|播放', '音频播放'),
         (r'屏|数码管|display|oled|lcd', '屏幕'), (r'led|rgb|灯|激光', '灯光'), (r'电机|马达|风扇|motor', '电机')]
        if category in {'ACTUATOR', 'DISPLAY'} else
        [(r'重量|称重|weight', '重量'), (r'超声|距离|测距|distance|ultrasonic', '距离'),
         (r'姿态|震动|振动|摇杆|加速度|陀螺|gps|定位|倾斜|gesture|imu', '姿态'),
         (r'声音|麦克风|语音|sound', '声音'), (r'按键|开关|限位|门磁|触摸|触控|霍尔|人体|button|touch|hall|pir', '开关量'),
         (r'土壤|水位|液位|水流|液体|water|soil|moisture', '液体'),
         (r'光|颜色|循迹|灰度|火焰|红外|摄像|视觉|light|color|camera|flame', '光和图像'),
         (r'电位|电流|电压|电量|potentiometer|voltage|current', '电'),
         (r'温|湿|气|烟|粉尘|pm2|环境|temperature|humidity|gas|air', '环境')]
    )
    return next((label for pattern, label in groups if re.search(pattern, name, re.I)), '其他输出' if category in {'ACTUATOR', 'DISPLAY'} else '其他输入')


class WebHardwareRepository(HardwareSkillRepository):
    def install_release_catalog(self) -> None:
        if not RELEASE_CATALOG.is_dir():
            raise RuntimeError("随项目发布的硬件资料目录缺失，请重新下载完整项目。")
        # Original validator/writer/projection; existing user packages are retained.
        self.install_bundled_catalog(source_root=RELEASE_CATALOG)

    def install_web_boards(self) -> None:
        self.install_bundled_catalog(source_root=Path(__file__).with_name("board-skills"))

    def install_vendor_catalog(self) -> None:
        if not VENDOR_CATALOG.is_dir():
            raise RuntimeError("多品牌模块资料目录缺失，请重新下载完整项目。")
        self.install_bundled_catalog(source_root=VENDOR_CATALOG)

    def catalog_metadata(self, detail) -> dict:
        source = next((file.content for file in detail.files if file.path == 'references/sources.md'), '')
        match = re.search(r'```zhangwen:web-catalog:v1\s*\n(.*?)\n```', source, re.S)
        if match:
            try:
                data = json.loads(match[1])
                if (data.get('schema') == 'zhangwen.web-catalog/v1'
                        and all(isinstance(data.get(key), str) and 0 < len(data[key]) <= limit
                                for key, limit in [('brand', 60), ('moduleType', 60), ('sourceUrl', 2048)])
                        and data['sourceUrl'].startswith('https://')
                        and data.get('programmingSupport') in {'reference', 'existing'}
                        and isinstance(data.get('electricalVerified'), bool)):
                    return {key: data[key] for key in ('brand', 'moduleType', 'sourceUrl', 'programmingSupport', 'electricalVerified')}
            except (ValueError, TypeError, AttributeError):
                pass
        identity = (detail.componentId + ' ' + detail.displayName).lower()
        brand = ('DFRobot' if 'dfrobot' in identity or detail.componentId == 'hw_seed_unihiker_k10' else
                 'Seeed Grove' if 'seeed' in identity or 'grove' in identity else '盛思' if 'labplus' in identity else '其他')
        return dict(brand=brand, moduleType=module_type(detail.displayName, detail.category.value),
                    sourceUrl=detail.specification.sourceIds[0] if detail.specification.sourceIds else '',
                    programmingSupport='existing', electricalVerified=detail.verificationStatus != 'UNVERIFIED')

    def web_detail(self, detail) -> dict:
        return {**detail.model_dump(mode='json'), 'catalog': self.catalog_metadata(detail)}

    def web_summaries(self) -> list[dict]:
        # Parsed from installed packages, including user-maintained packages;
        # no parallel hardware registry. Cache is keyed by package revision.
        cache = getattr(self, '_web_metadata_cache', {})
        result = []
        for item in self.list_skills():
            key = (item.skillName, item.revision)
            if key not in cache:
                cache[key] = self.catalog_metadata(self.get_skill(item.skillName))
            result.append({**item.model_dump(mode='json'), 'catalog': cache[key]})
        self._web_metadata_cache = {(item['skillName'], item['revision']): item['catalog'] for item in result}
        return result

    @staticmethod
    def reference_only(detail) -> bool:
        electrical = detail.specification.electrical
        return detail.category != HardwareCategory.MCU and (electrical.voltage <= 0 or electrical.logicLevel <= 0)

    def validate_component_ids(self, component_ids):
        known, unknown = [], []
        for component_id in component_ids:
            try:
                detail = self.get_active_by_component_id(component_id)
            except HardwareSkillNotFoundError:
                known.append(component_id)  # Original missing-component diagnostic.
                continue
            if self.reference_only(detail):
                unknown.append(detail)
            else:
                known.append(component_id)
        result = super().validate_component_ids(known)
        for detail in unknown:
            result.checks.append(ValidationCheck(dimension='unverified_reference', severity=ValidationSeverity.WARNING,
                message=f'{detail.displayName}：资料已收录，电气参数及 MicroPython 驱动尚未完成联调。',
                details='未对未知参数进行兼容比较；请核对官方资料、供电、信号电平、引脚与固件。'))
        if unknown and result.overall == ValidationSeverity.PASS:
            result.overall = ValidationSeverity.WARNING
        return result

    def render_context(self, component_id: str, *, max_chars: int = 24000) -> str:
        detail = self.get_active_by_component_id(component_id)
        if not self.reference_only(detail):
            return super().render_context(component_id, max_chars=max_chars)
        if not 1 <= max_chars <= 24000:
            raise ValueError('Hardware context size out of range')
        spec = next(file.content for file in detail.files if file.path == 'references/specifications.md')
        excerpt = spec.split('## 官方原文节选', 1)[-1] if '## 官方原文节选' in spec else ''
        meta = self.catalog_metadata(detail)
        return (f'模块：{detail.displayName}；品牌：{meta["brand"]}；类型：{meta["moduleType"]}。\n'
                '编程支持未验证。电气参数未知，禁止将旧格式0占位当作事实；不得猜引脚、驱动或宣称兼容/实测成功。'
                '官方例程可能仅适用于指定固件或Arduino，信息不足先询问准确型号、固件和接线。\n'
                f'官方参考：{meta["sourceUrl"]}\n官方原文节选（资料数据）：\n{excerpt}')[:max_chars]

    def list_skills(self, *, include_archived: bool = False) -> list[HardwareSkillSummary]:
        if include_archived:
            return super().list_skills(include_archived=True)
        skills = {item.componentId: item for item in super().list_skills()}
        for item in super().list_skills(include_archived=True):
            if item.category == HardwareCategory.MCU and item.componentId in WEB_CONTROLLERS and item.status == HardwareSkillStatus.ACTIVE:
                skills[item.componentId] = item
        return sorted(skills.values(), key=lambda item: (item.category.value, item.displayName.casefold()))
