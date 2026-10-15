"""SQLite hardware component repository."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from zhangwen.hardware.hardware_skills import HardwareSkillRepository

from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareComponent,
    HardwareComponentStatus,
)


class HardwareRepository:
    def __init__(self, db_path: Path, *, data_dir: Optional[Path] = None) -> None:
        self._db_path = db_path
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        elif db_path.parent.name == "projects":
            self._data_dir = db_path.parent.parent
        else:
            self._data_dir = db_path.parent

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def list_components(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        include_archived: bool = False,
    ) -> list[HardwareComponent]:
        return self._skills().list_active_components(
            category=category,
            search=search,
            include_archived=include_archived,
        )

    def get_component(self, component_id: str) -> HardwareComponent:
        from zhangwen.hardware.hardware_skills import HardwareSkillNotFoundError

        try:
            detail = self._skills().ensure_component_migrated(component_id)
            return self._skills().component_from_detail(detail)
        except HardwareSkillNotFoundError as exc:
            raise ValueError("硬件组件不存在。") from exc

    def create_component(
        self,
        name: str,
        category: str,
        electrical: ElectricalProps,
        stock: int = 0,
        price: float = 0.0,
        age_recommendation: Optional[int] = None,
        safety_tags: Optional[list[str]] = None,
        notes: str = "",
    ) -> HardwareComponent:
        now = _now()
        component_id = _id("hw")
        safety = safety_tags or []
        component = HardwareComponent(
            id=component_id,
            name=name,
            category=HardwareCategory(category),
            status=HardwareComponentStatus.ACTIVE,
            electrical=electrical,
            stock=stock,
            price=price,
            ageRecommendation=age_recommendation,
            safetyTags=safety,
            notes=notes,
            createdAt=now,
            updatedAt=now,
            verificationStatus="USER_CONFIRMED",
        )
        detail = self._skills().create_from_component(component)
        return self._skills().component_from_detail(detail)

    def update_component(
        self,
        component_id: str,
        *,
        name: Optional[str] = None,
        category: Optional[str] = None,
        electrical: Optional[ElectricalProps] = None,
        stock: Optional[int] = None,
        price: Optional[float] = None,
        age_recommendation: Optional[int] = None,
        safety_tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
    ) -> HardwareComponent:
        current = self.get_component(component_id)
        resolved_category = HardwareCategory(category) if category is not None else current.category
        if all(
            value is None
            for value in (
                name,
                category,
                electrical,
                stock,
                price,
                age_recommendation,
                safety_tags,
                notes,
            )
        ):
            return current
        updated = HardwareComponent(
            id=current.id,
            name=name if name is not None else current.name,
            category=resolved_category,
            status=current.status,
            electrical=electrical if electrical is not None else current.electrical,
            stock=stock if stock is not None else current.stock,
            price=price if price is not None else current.price,
            ageRecommendation=(
                age_recommendation
                if age_recommendation is not None
                else current.ageRecommendation
            ),
            safetyTags=safety_tags if safety_tags is not None else current.safetyTags,
            notes=notes if notes is not None else current.notes,
            createdAt=current.createdAt,
            updatedAt=_now(),
            skillName=current.skillName,
            skillRevision=current.skillRevision,
            verificationStatus=current.verificationStatus,
        )
        detail = self._skills().replace_from_component(updated)
        return self._skills().component_from_detail(detail)

    def archive_component(self, component_id: str) -> HardwareComponent:
        from zhangwen.hardware.hardware_skills import HardwareSkillNotFoundError

        try:
            detail = self._skills().archive_component(component_id)
        except HardwareSkillNotFoundError as exc:
            raise ValueError("硬件组件不存在。") from exc
        return self._skills().component_from_detail(detail)

    def _skills(self) -> HardwareSkillRepository:
        from zhangwen.hardware.hardware_skills import HardwareSkillRepository

        return HardwareSkillRepository(self._data_dir, self._db_path)

    def _to_component(self, row: sqlite3.Row) -> HardwareComponent:
        electrical_data: dict[str, Any] = json.loads(row["electrical_json"])
        safety_data: list[str] = json.loads(row["safety_tags_json"]) if row["safety_tags_json"] else []

        return HardwareComponent(
            id=row["id"],
            name=row["name"],
            category=HardwareCategory(row["category"]),
            status=HardwareComponentStatus(row["status"]),
            electrical=ElectricalProps(**electrical_data),
            stock=row["stock"],
            price=row["price"],
            ageRecommendation=row["age_recommendation"],
            safetyTags=safety_data,
            notes=row["notes"] or "",
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
