# TF 卡、录音和播放 API

## TF 卡

验证级别：D。

```python
from k10_base import TF_card
import os

tf_card = TF_card()
print(os.listdir("/sd"))
```

官方示例使用的挂载路径：

```text
/sd
```

## 录音与播放

验证级别：D；文件兼容性为 C。

```python
from unihiker_k10 import mic, speaker
```

录制到系统存储：

```python
mic.recode_sys(name="sound.wav", time=5)
```

播放系统存储：

```python
speaker.play_sys_music("sound.wav")
```

录制到 TF 卡：

```python
mic.recode_tf(name="sound.wav", time=5)
```

播放 TF 卡：

```python
speaker.play_tf_music("sound.wav")
```

## 使用约束

- 录音时长参数名为 `time`。
- 使用 TF 卡前先确认 `/sd` 可访问。
- TF 卡质量可能影响 AI 与存储组合的稳定性。
- 官方 FAQ 指出，TF 卡中的 WAV 播放异常时应检查文件格式，建议使用未压缩双声道 WAV。
- 在线程中播放音频时，不要在播放过程中强行停止线程。
