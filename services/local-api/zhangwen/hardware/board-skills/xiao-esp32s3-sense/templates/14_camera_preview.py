# Camera APIs differ between MicroPython builds for XIAO ESP32S3 Sense.
# Run 00_profile_probe.py first and adapt this file only when the fixed firmware
# manifest identifies a compatible camera module and its exact API.
raise RuntimeError("camera API is not declared by the active firmware profile")
