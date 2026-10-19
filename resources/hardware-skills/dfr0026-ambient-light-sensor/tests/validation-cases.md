# DFR0026 本地验证用例

```zhangwen:hardware-validation:v1
{
  "schema": "zhangwen.hardware-validation/v1",
  "cases": [
    {
      "id": "canonical-self-smoke",
      "components": ["$self"],
      "expectedOverall": ["PASS", "WARNING", "FAIL"]
    }
  ]
}
```

## 人工验收

1. 校验 `models/cadquery.py` 的 SHA-256 与 `mechanical.md` 一致。
2. 校验封面图片 SHA-256 与 `manifest.json` 一致。
3. 检查 3.3 V 与 5 V 两种供电场景下的最强光输出电压。
4. 对目标主控运行 MicroPython ADC 示例，记录暗、室内、强光三档原始值。
5. 确认更亮时读数增大；若方向相反，记录板卡和固件差异。
6. 用卡尺复核 PCB 长宽、两孔中心和接线口尺寸，解决 20 mm 与 22 mm 宽度冲突。
7. 只有在单独受控环境验证 CadQuery 后，才能把模型状态提升为 `VERIFIED_REFERENCE`。

