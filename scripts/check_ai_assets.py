from pathlib import Path
import filecmp
import sys

root = Path(__file__).resolve().parents[1]
source = root / "ai" / "skills"
failed = False
for target in [root / ".agents" / "skills", root / ".qoder" / "skills"]:
    cmp = filecmp.dircmp(source, target)
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        failed = True
        print(f"Drift detected: {target}")
        print("left_only", cmp.left_only, "right_only", cmp.right_only, "diff", cmp.diff_files)
if failed:
    print("Run: python scripts/sync_ai_assets.py")
    sys.exit(1)
print("Shared Skills are in sync.")
