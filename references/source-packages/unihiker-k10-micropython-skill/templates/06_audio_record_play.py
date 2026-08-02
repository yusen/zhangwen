"""K10 系统存储录音与播放。"""

import time
from unihiker_k10 import mic, speaker

FILENAME = "sound.wav"
RECORD_SECONDS = 3

try:
    print("recording:", FILENAME)
    mic.recode_sys(name=FILENAME, time=RECORD_SECONDS)
    print("recording done")

    time.sleep(1)

    print("playing:", FILENAME)
    speaker.play_sys_music(FILENAME)
    print("playback done")

except Exception as exc:
    print("audio operation failed:", repr(exc))
