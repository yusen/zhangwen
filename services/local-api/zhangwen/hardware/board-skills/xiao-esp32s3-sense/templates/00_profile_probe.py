import machine
import sys

print("implementation:", sys.implementation)
print("machine:", machine)
print("frequency:", machine.freq())

for module_name in ("camera", "sdcard", "audio"):
    try:
        module = __import__(module_name)
        print(module_name, "available", dir(module))
    except ImportError:
        print(module_name, "unavailable")
