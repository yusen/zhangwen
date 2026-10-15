"""Load and verify the immutable ZW-MPY-SIM runtime package manifest."""

from __future__ import annotations

import hashlib
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from zhangwen.domains.simulation.runtime.models import (
    NativeCoreState,
    NativeCoreVerification,
    NativeRuntimeDistribution,
    SimulationRuntimeManifest,
    SimulationRuntimeStatus,
)


MICROPYTHON_UPSTREAM_COMMIT = "647c8b96cae7e202c7a020395b7cfe65e5b8ce04"
MICROPYTHON_SOURCE_ARCHIVE_SHA256 = (
    "12be6514df6272c0fcb328122b534af6b12abdd52435c19f40ee1707cc43ac98"
)
_RUNTIME_DIR = Path(__file__).resolve().parent
_MANIFEST_PATH = _RUNTIME_DIR / "runtime-manifest.json"


@dataclass(frozen=True)
class SimulationRuntimePackage:
    manifest: SimulationRuntimeManifest

    @classmethod
    def load_builtin(cls) -> SimulationRuntimePackage:
        manifest = SimulationRuntimeManifest.model_validate_json(
            _MANIFEST_PATH.read_text(encoding="utf-8")
        )
        if manifest.micropython.upstream_commit != MICROPYTHON_UPSTREAM_COMMIT:
            raise RuntimeError("ZW-MPY-SIM manifest MicroPython commit drifted.")
        if (
            manifest.micropython.source_archive_sha256
            != MICROPYTHON_SOURCE_ARCHIVE_SHA256
        ):
            raise RuntimeError("ZW-MPY-SIM manifest source digest drifted.")
        for notice in manifest.license_notice_paths:
            path = (_RUNTIME_DIR / notice).resolve(strict=False)
            if _RUNTIME_DIR not in path.parents or not path.is_file():
                raise RuntimeError(f"ZW-MPY-SIM license notice is missing: {notice}")
        return cls(manifest=manifest)

    @property
    def platform_id(self) -> str:
        machine = platform.machine().casefold()
        architecture = "x86_64" if machine in {"amd64", "x86_64"} else machine
        if sys.platform == "win32":
            return f"windows-{architecture}"
        if sys.platform.startswith("linux"):
            return f"linux-{architecture}"
        if sys.platform == "darwin":
            return f"macos-{architecture}"
        return f"{sys.platform}-{architecture}"

    def distribution(self) -> NativeRuntimeDistribution | None:
        return next(
            (
                item
                for item in self.manifest.native_distributions
                if item.platform == self.platform_id
            ),
            None,
        )

    def native_executable(self, data_dir: Path) -> Path | None:
        distribution = self.distribution()
        if distribution is None:
            return None
        root = (Path(data_dir) / "runtime-packages" / "zw-mpy-sim" / "1").resolve(
            strict=False
        )
        target = (root / distribution.relative_path).resolve(strict=False)
        if root not in target.parents:
            raise RuntimeError("ZW-MPY-SIM native executable escaped package root.")
        return target

    def status(self, data_dir: Path) -> SimulationRuntimeStatus:
        distribution = self.distribution()
        if distribution is None:
            native = NativeCoreVerification(
                status=NativeCoreState.NOT_PROVISIONED,
                verified=False,
                platform=self.platform_id,
                relativePath=None,
                expectedSha256=None,
                actualSha256=None,
                message=(
                    "当前安装包未提供通过摘要固定的 MicroPython host core；"
                    "原生模式不会回退到参考 Worker。"
                ),
            )
        else:
            executable = self.native_executable(data_dir)
            assert executable is not None
            native = self.verify_executable(
                executable,
                distribution.sha256,
                relative_path=distribution.relative_path,
            )
        return SimulationRuntimeStatus(
            runtimePackageRevisionId=self.manifest.revision_id,
            micropythonVersion=self.manifest.micropython.version,
            upstreamCommit=self.manifest.micropython.upstream_commit,
            workerProtocol=self.manifest.worker_protocol,
            nativeCore=native,
            behavioralReferenceAvailable=True,
            behavioralReferenceEvidenceEligible=False,
            supportedApis=self.manifest.supported_apis,
            supportedComponents=self.manifest.supported_components,
            explicitlyUnsupported=self.manifest.explicitly_unsupported,
            knownLimitations=[
                "行为参考层不是 MicroPython core，不能创建原生 MicroPython 或项目 Evidence。",
                "不模拟电流、损坏、射频、周期精确时序或具体商品板完整行为。",
                "原生 core 只有在平台二进制被 manifest 摘要固定且校验通过后才可启动。",
            ],
        )

    def verify_executable(
        self,
        executable: Path,
        expected_sha256: str,
        *,
        relative_path: str | None = None,
    ) -> NativeCoreVerification:
        target = Path(executable)
        reported_path = relative_path or target.name
        if not target.is_file():
            return NativeCoreVerification(
                status=NativeCoreState.MISSING,
                verified=False,
                platform=self.platform_id,
                relativePath=reported_path,
                expectedSha256=expected_sha256,
                actualSha256=None,
                message="固定 MicroPython host core 文件不存在。",
            )
        digest = hashlib.sha256()
        try:
            with target.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return NativeCoreVerification(
                status=NativeCoreState.MISSING,
                verified=False,
                platform=self.platform_id,
                relativePath=reported_path,
                expectedSha256=expected_sha256,
                actualSha256=None,
                message="固定 MicroPython host core 无法读取。",
            )
        actual = digest.hexdigest()
        verified = actual == expected_sha256
        return NativeCoreVerification(
            status=(
                NativeCoreState.VERIFIED
                if verified
                else NativeCoreState.INTEGRITY_FAILED
            ),
            verified=verified,
            platform=self.platform_id,
            relativePath=reported_path,
            expectedSha256=expected_sha256,
            actualSha256=actual,
            message=(
                "固定 MicroPython host core 摘要校验通过。"
                if verified
                else "固定 MicroPython host core 摘要不匹配，已拒绝启动。"
            ),
        )
