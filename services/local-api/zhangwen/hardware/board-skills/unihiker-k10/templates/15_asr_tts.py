"""K10 离线语音识别与语音合成。"""

import time
import asr

pending_command = None


def on_asr(command_id):
    global pending_command
    pending_command = command_id


asr.init_asr()
asr.set_asr_callback(on_asr)
asr.add_asr_command(1, "kai deng")
asr.add_asr_command(2, "guan deng")
asr.start_asr()
asr.start_tts()

print("请说唤醒词，然后说：开灯 或 关灯")

try:
    while True:
        if pending_command is not None:
            command_id = pending_command
            pending_command = None

            print("ASR command ID:", command_id)

            if command_id == 1:
                asr.add_tts_data("灯光已打开")
            elif command_id == 2:
                asr.add_tts_data("灯光已关闭")
            else:
                asr.add_tts_data("未识别的命令")

        time.sleep_ms(20)

except KeyboardInterrupt:
    print("ASR stopped")

finally:
    asr.free_asr()
