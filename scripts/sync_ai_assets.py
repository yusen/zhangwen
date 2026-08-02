from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "ai" / "skills"
targets = [root / ".agents" / "skills", root / ".qoder" / "skills"]
for target in targets:
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for skill in source.iterdir():
        if skill.is_dir():
            shutil.copytree(skill, target / skill.name)
print("Skills synchronized to Codex and Qoder discovery paths.")
