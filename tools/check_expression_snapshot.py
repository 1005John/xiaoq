"""Check the pinned expression runtime before product integration or deployment."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "vendor/hardware_expression_system"
EXPECTED_SHA256 = "61de8bd62e774562234b8e5663f7d8f24873c638a8d0f9eda8925b238d0c7d5d"
EXPECTED_FILES = 23


def package_digest(root: Path) -> tuple[int, str]:
    files = sorted(root.rglob("*.py"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return len(files), digest.hexdigest()


if __name__ == "__main__":
    count, actual = package_digest(ROOT)
    if (count, actual) != (EXPECTED_FILES, EXPECTED_SHA256):
        raise SystemExit(
            f"Expression snapshot changed: files={count}, sha256={actual}. "
            "Update the independent expression project and review a new pinned release."
        )
    print(f"Expression snapshot OK: {count} Python files, sha256={actual}")
