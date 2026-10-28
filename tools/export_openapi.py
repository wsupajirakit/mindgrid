#!/usr/bin/env python3
"""Write web/openapi/openapi.json from the backend app (--check: fail when it is stale).
The web types (`npm run gen:api`) are generated from it.
Run with the backend venv: backend/.venv/bin/python tools/export_openapi.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "web" / "openapi" / "openapi.json"
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("MINDGRID_SECRET_KEY", "openapi-export-only-" + "x" * 32)
# The snapshot is the default API shape; a local brand override must not leak into it.
for name in [k for k in os.environ if k.startswith("MINDGRID_BRAND_")]:
    del os.environ[name]

from mindgrid.app import create_app  # noqa: E402


def render() -> str:
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        stale = not SNAPSHOT.exists() or SNAPSHOT.read_text(encoding="utf-8") != text
        print(f"{SNAPSHOT.relative_to(ROOT)}: {'stale' if stale else 'current'}")
        return 1 if stale else 0
    SNAPSHOT.write_text(text, encoding="utf-8")
    print(f"wrote {SNAPSHOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
