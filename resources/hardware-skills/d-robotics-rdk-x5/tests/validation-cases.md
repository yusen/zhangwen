# 本地验证用例

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

1. 在标准版 RDK X5 上确认 RDK OS 版本、`GPIO.model`、BOARD 编号、GPIO 和 PWM 示例；未执行前不得声称实板通过。
2. 用受限流电源和合格 Type-C 线记录空闲、CPU/BPU、相机、USB 与无线组合负载的输入电压、峰值电流和温升。
3. 核对 40PIN 的 3.3 V/5 V 轨、最大 3.46 V IO、复用关系以及多接口同时负载的压降。
4. 断电验证 MIPI CSI、MIPI DSI、HDMI、CAN FD、USB、音频、microSD、以太网/PoE 和天线连接。
5. 用官方 2D/3D 资料或实物测量复核安装孔中心、接口开口、散热、天线和线缆禁布区。
6. 使用掌问实际 `HardwareSkillRepository.get_skill()` 加载本包，并确认 `list_active_components()` 返回同一 componentId 与 revision；当前未执行。
