"""Debounced external-editor synchronization for package workspaces."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchfiles import awatch

from zhangwen.domains.packages.models import PackagePlatformError
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.domains.packages.service import PackagePlatformService


logger = logging.getLogger(__name__)


class PackageWorkspaceWatcher:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._root = (self._data_dir / "package-workspaces").resolve(strict=False)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._root.mkdir(parents=True, exist_ok=True)
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._run(),
            name=f"package-workspace-watcher-{id(self)}",
        )
        # Give the native watcher one bounded scheduling slice to establish its
        # baseline before callers are allowed to write immediately after start.
        await asyncio.sleep(0.075)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def _run(self) -> None:
        async for changes in awatch(
            self._root,
            debounce=150,
            step=50,
            stop_event=self._stop_event,
        ):
            workspace_ids = {
                workspace_id
                for _, changed_path in changes
                if (workspace_id := self._workspace_id(changed_path)) is not None
            }
            for workspace_id in sorted(workspace_ids):
                await asyncio.to_thread(self._sync_workspace, workspace_id)

    def _workspace_id(self, changed_path: str) -> str | None:
        candidate = Path(changed_path).resolve(strict=False)
        try:
            relative = candidate.relative_to(self._root)
        except ValueError:
            return None
        return relative.parts[0] if len(relative.parts) >= 2 else None

    def _sync_workspace(self, workspace_id: str) -> None:
        repository = PackagePlatformRepository(self._data_dir)
        try:
            owner_subject = repository.workspace_owner_subject(workspace_id)
            PackagePlatformService(
                self._data_dir,
                owner_subject=owner_subject,
            ).sync_external_workspace(workspace_id)
        except PackagePlatformError as exc:
            logger.warning(
                "Package workspace external sync was rejected for %s: %s",
                workspace_id,
                exc,
            )
        except (OSError, UnicodeError) as exc:
            logger.warning(
                "Package workspace external sync failed for %s: %s",
                workspace_id,
                exc,
            )


_WATCHERS: dict[Path, PackageWorkspaceWatcher] = {}


def package_workspace_watcher(data_dir: Path) -> PackageWorkspaceWatcher:
    key = Path(data_dir).resolve(strict=False)
    watcher = _WATCHERS.get(key)
    if watcher is None:
        watcher = PackageWorkspaceWatcher(key)
        _WATCHERS[key] = watcher
    return watcher


async def stop_package_workspace_watchers() -> None:
    watchers = list(_WATCHERS.values())
    _WATCHERS.clear()
    await asyncio.gather(*(watcher.stop() for watcher in watchers))
