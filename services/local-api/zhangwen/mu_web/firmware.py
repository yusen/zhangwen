"""Firmware selection metadata only; flashing is browser-only and user-triggered."""
PROFILES = {
    "hw_labplus_mpython_v2": ("ESP32", 0x1000, "https://mpython.readthedocs.io/zh-cn/master/"),
    "hw_labplus_mpython_esp32s3_v3": ("ESP32-S3", 0, "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/"),
    "hw_seed_unihiker_k10": ("ESP32-S3", 0, "https://www.unihiker.com/wiki/k10"),
    "hw_seeed_xiao_esp32s3_sense": ("ESP32-S3", 0, "https://wiki.seeedstudio.com/xiao_esp32s3_micropython/"),
    "hw_esp32_generic_c3": ("ESP32-C3", 0, "https://micropython.org/download/ESP32_GENERIC_C3/"),
}


def firmware_profile(board_id):
    chip, offset, documentation = PROFILES[board_id]
    return {"boardId": board_id, "chip": chip, "offset": offset, "documentation": documentation}
