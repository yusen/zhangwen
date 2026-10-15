"""Build the two new directory-backed packages using the preserved validator.

Only a disposable V4 data directory is used. Production is installed at startup.
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/local-api"))
from zhangwen.mu_web.repository import MuRepository
from zhangwen.hardware.models import ElectricalProps, HardwareCategory, HardwareSkillSpecification


CIRCLE = '''# 掌控板 2.0 · OLED 空心圆
from mpython import oled

oled.fill(0)
oled.circle(64, 32, 24, 1)
oled.show()
print("ZW_CIRCLE_OK: center=(64,32), radius=24, outline")
'''


def main():
    (ROOT / ".test-data").mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="board-packages-", dir=ROOT / ".test-data"))
    repo = MuRepository(target)
    packages = [
        ("esp32-generic-c3", "hw_esp32_generic_c3", "ESP32-C3（通用 MicroPython）",
         "ESP32-C3 通用 MicroPython 主控；具体开发板引脚和板载外设请按实物核对。",
         "ESP32_GENERIC_C3 MicroPython，GPIO 为 3.3V；USB供电经过开发板稳压。通用芯片档案不声明板载 LED、屏幕或开发板别名引脚。峰值电流未固化，0为未知占位。",
         "machine", "ESP32_GENERIC_C3 MicroPython；4MB及以上Flash，USB串口支持取决于接线与板卡",
         "https://micropython.org/download/ESP32_GENERIC_C3/",
         "原生USB串口使用GPIO18/19；若板卡使用USB-UART桥，按桥接串口连接。不自动安装固件、不切换引导模式。\nMicroPython 示例只使用通用 API：`import sys; print(sys.platform)`。外设端口须先核对开发板。",
         'import sys\nprint(sys.platform)\n'),
        ("labplus-mpython-v2", "hw_labplus_mpython_v2", "掌控板 2.0（ESP32）",
         "掌控板 2.0，128×64 单色 OLED，使用官方 mPython 固件和 oled 绘图 API。",
         "经典掌控板 ESP32 / 128×64 OLED，3.3V逻辑，USB供电。使用 mpython.oled，不使用掌控3.0的display/LCD API。具体2.x批次传感器可能不同。峰值电流未固化，0为未知占位。",
         "mpython", "掌控板2.x官方mPython MicroPython固件，含mpython.oled",
         "https://mpython.readthedocs.io/en/master/library/mPython/mpython.html",
         "板载入口：`from mpython import oled`。OLED为128×64单色：`oled.fill(0)`清屏，`oled.circle(x,y,r,1)`绘制空心圆，`oled.show()`刷新。勿用`fill_circle`替代空心圆。\n官方源码：https://github.com/labplus-cn/mpython/blob/master/port/boards/mpython/modules/mpython.py\n程序返回REPL后画面仍保持；实际点亮与屏幕结果需实物观察。",
         CIRCLE),
    ]
    for slug, component, name, description, notes, driver, firmware, source, integration, example in packages:
        spec = HardwareSkillSpecification(componentId=component, name=name, category=HardwareCategory.MCU,
            electrical=ElectricalProps(voltage=3.3, logicLevel=3.3, peakCurrent=0,
                communicationProtocol="GPIO", driverName=driver, firmwareRequirement=firmware),
            safetyTags=["3.3V逻辑", "USB供电", "无自动烧录"], notes=notes,
            verificationStatus="OFFICIAL_API_REFERENCE_UNTESTED", sourceIds=[source])
        detail = repo.skills.create_skill(spec, skill_name=slug, description=description,
            migrated_sections={
                "references/integration.md": "\n\n## 官方API边界\n" + integration + "\n",
                "references/sources.md": "\n\n## 来源（2026-10-14）\n" + source + "\n",
                "examples/usage.md": "\n\n## 最小示例\n```python\n" + example + "```\n",
            })
        destination = ROOT / "services/local-api/zhangwen/mu_web/board-skills" / slug
        if destination.exists():
            raise RuntimeError("Package already exists: " + slug)
        shutil.copytree(target / "hardware-skills" / slug, destination)
        print(slug, detail.revision)
    examples = ROOT / "examples/mpython-v2-circle"
    examples.mkdir(parents=True, exist_ok=True)
    (examples / "main.py").write_text(CIRCLE, encoding="utf-8")


if __name__ == "__main__":
    main()
