"""Board-specific code references, kept separate from immutable legacy packages."""
from pathlib import Path

SKILLS = {"hw_labplus_mpython_v2": "mpython-v2", "hw_labplus_mpython_esp32s3_v3": "mpython-v3"}


def programming_context(board_id: str) -> str:
    name = SKILLS.get(board_id)
    if not name:
        return ""
    root = Path(__file__).with_name("programming-skills") / name
    return "\n".join((root / file).read_text(encoding="utf-8") for file in ("SKILL.md", "references/api.md"))
