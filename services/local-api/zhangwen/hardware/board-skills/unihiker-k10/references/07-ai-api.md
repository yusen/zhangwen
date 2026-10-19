# AI 与语音 API

## 通用图像 AI 流程

验证级别：D；模式组合与切换为 C。

```python
import ai
from unihiker_k10 import screen

ai.init_ai()
ai.camera_start()
# 选择一种模式
screen.init()
```

循环：

```python
image_data = ai.camera_capture()
screen.show_camera_img(image_data)

if ai.is_ai_data_updated():
    data = ai.get_ai_data()
```

释放：

```python
ai.deinit_ai()
```

## 移动检测

```python
ai.move_detect()
```

结果字段：

```python
data["move_flag"]
```

## 二维码识别

```python
ai.code_scanner()
```

结果字段：

```python
data["code_data"]
```

## 猫脸检测

```python
ai.cat_detect()
```

结果字段：

```python
data["cat_flag"]
data["cat_detect"]["frame_length"]
data["cat_detect"]["frame_width"]
```

嵌套字段只有在 `cat_flag` 为真时读取。

## 人脸识别

```python
ai.face_recognize_start()
```

注册和识别：

```python
ai.register_face()
ai.recognize_face()
```

结果字段：

```python
data["face_flag"]
data["face_detect"]["face_id"]
data["face_detect"]["left_eye"]
```

嵌套字段只有在 `face_flag` 为真时读取。

## 语音识别和合成

```python
import asr
```

初始化：

```python
asr.init_asr()
```

官方页面还给出带检测时长与模式的形式：

```python
asr.init_asr(6000, asr.ASR_MODE_SINGLE)
```

模式常量：

```python
asr.ASR_MODE_SINGLE
asr.ASR_MODE_CONTINUOUS
```

命令词：

```python
asr.add_asr_command(1, "kai deng")
```

回调：

```python
def on_asr(command_id):
    print("ID:", command_id)

asr.set_asr_callback(on_asr)
```

启动：

```python
asr.start_asr()
asr.start_tts()
```

合成文本：

```python
asr.add_tts_data("灯光已打开")
```

释放：

```python
asr.free_asr()
```

## AI 安全规则

- 一次只启用一个视觉识别模式。
- 不在主循环中重复调用 `init_ai()`、`camera_start()` 或模式函数。
- 模式切换必须有状态机和冷却时间。
- 回调中不做屏幕和高内存操作。
- 捕获异常或 Ctrl+C 后释放 AI/ASR 资源。
