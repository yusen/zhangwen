"""Data-only built-in S3/C3 board and component catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from zhangwen.domains.simulation.models import (
    SimulationBoardProfile,
    SimulationCatalogView,
    SimulationComponentProfile,
)


_CATALOG_DIR = Path(__file__).with_name("catalog")


@dataclass(frozen=True)
class SimulationCatalog:
    boards: list[SimulationBoardProfile]
    components: list[SimulationComponentProfile]

    @classmethod
    def load_builtin(cls) -> SimulationCatalog:
        payload = json.loads((_CATALOG_DIR / "catalog.json").read_text(encoding="utf-8"))
        view = SimulationCatalogView.model_validate(payload)
        licenses = json.loads(
            (_CATALOG_DIR / "licenses.json").read_text(encoding="utf-8")
        )
        licensed_paths = {
            str(item["path"])
            for item in licenses.get("entries", [])
            if isinstance(item, dict) and item.get("path")
        }
        for item in [*view.boards, *view.components]:
            relative = item.visual_asset.removeprefix("catalog/").split("#", 1)[0]
            if relative not in licensed_paths:
                raise RuntimeError(f"仿真视觉资源缺少许可清单：{relative}")
            if not (_CATALOG_DIR / relative).is_file():
                raise RuntimeError(f"仿真视觉资源不存在：{relative}")
        return cls(boards=view.boards, components=view.components)

    def view(self) -> SimulationCatalogView:
        return SimulationCatalogView(boards=self.boards, components=self.components)

    def board(self, revision_id: str) -> SimulationBoardProfile | None:
        return next(
            (item for item in self.boards if item.revision_id == revision_id), None
        )

    def component(self, revision_id: str) -> SimulationComponentProfile | None:
        return next(
            (item for item in self.components if item.revision_id == revision_id),
            None,
        )
