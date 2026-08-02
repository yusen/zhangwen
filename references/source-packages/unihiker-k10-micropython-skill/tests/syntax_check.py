"""在电脑上检查本包 Python 文件的语法，不执行 K10 专用导入。"""

from pathlib import Path
import py_compile
import sys

root = Path(__file__).resolve().parents[1]
errors = []

for path in sorted(root.rglob("*.py")):
    if "__pycache__" in path.parts:
        continue

    try:
        py_compile.compile(str(path), doraise=True)
        print("OK", path.relative_to(root))
    except Exception as exc:
        errors.append((path, exc))
        print("FAIL", path.relative_to(root), repr(exc))

if errors:
    sys.exit(1)

print("All Python files passed syntax compilation.")
