import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


service_root = Path(SPECPATH).resolve()
package_root = service_root / "zhangwen"

resource_directories = (
    "experts/agent-packages",
    "experts/prompts",
    "experts/skill-templates",
    "hardware/board-profiles",
    "hardware/board-skills",
    "hardware/bundled-hardware-skills",
    "hardware/catalog-assets",
)
datas = []
for relative_path in resource_directories:
    source_root = package_root / relative_path
    for source in source_root.rglob("*"):
        if (
            not source.is_file()
            or "__pycache__" in source.parts
            or source.suffix.lower() in {".pyc", ".pyo"}
        ):
            continue
        destination = Path("zhangwen") / relative_path / source.relative_to(source_root).parent
        datas.append((str(source), destination.as_posix()))
catalog_root = service_root / ".data" / "hardware-skills"
catalog_destination = Path("zhangwen/hardware/bundled-hardware-catalog/hardware-skills")
for source in catalog_root.rglob("*"):
    if not source.is_file() or source.is_symlink():
        continue
    destination = catalog_destination / source.relative_to(catalog_root).parent
    datas.append((str(source), destination.as_posix()))
catalog_manifest = os.environ.get("ZHANGWEN_HARDWARE_CATALOG_MANIFEST", "").strip()
if catalog_manifest:
    datas.append(
        (
            catalog_manifest,
            "zhangwen/hardware/bundled-hardware-catalog",
        )
    )
for distribution in ("esptool", "mpremote"):
    datas += copy_metadata(distribution)
datas += collect_data_files("certifi")
datas += collect_data_files("esptool")

hidden_imports = sorted(
    {
        *collect_submodules("esptool"),
        *collect_submodules("mpremote"),
        *collect_submodules("serial.tools"),
        "anyio._backends._asyncio",
        "bitstring.bitstore_bitarray",
        "bitstring.bitstore_bitarray_helpers",
        "bitstring.bitstore_common_helpers",
        "serial.serialwin32",
        "zhangwen.code_agent.validation_worker",
        "uvicorn.lifespan.on",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
    }
)

a = Analysis(
    [str(package_root / "packaged_entry.py")],
    pathex=[str(service_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_asyncio", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="zhangwen-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="zhangwen-sidecar",
)
