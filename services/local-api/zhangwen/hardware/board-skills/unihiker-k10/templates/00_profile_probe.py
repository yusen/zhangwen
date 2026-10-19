"""行空板 K10 MicroPython 固件与模块探测。"""

MODULES = (
    "unihiker_k10",
    "k10_base",
    "ai",
    "asr",
)

print("UNIHIKER K10 MicroPython profile probe")

for module_name in MODULES:
    try:
        module = __import__(module_name)
        print("OK:", module_name)
        print("members:", dir(module))
    except Exception as exc:
        print("FAIL:", module_name, repr(exc))
