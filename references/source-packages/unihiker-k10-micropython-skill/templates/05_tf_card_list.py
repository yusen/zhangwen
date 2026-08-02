"""K10 TF 卡文件列表。"""

import os
from k10_base import TF_card

try:
    tf_card = TF_card()
    files = os.listdir("/sd")
    print("Files in /sd:")
    for filename in files:
        print("-", filename)
except Exception as exc:
    print("TF card access failed:", repr(exc))
    print("Check card insertion, format and firmware support.")
