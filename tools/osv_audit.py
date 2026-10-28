#!/usr/bin/env python3
"""Check every locked package (backend/uv.lock) against the OSV advisory database.
Stdlib only: one POST to https://api.osv.dev/v1/querybatch. Exits 1 on any advisory.
Run: python3 tools/osv_audit.py
"""

import json
import sys
import tomllib
import urllib.request
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / "backend" / "uv.lock"
OSV = "https://api.osv.dev/v1/querybatch"


def pins() -> list[tuple[str, str]]:
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    out = []
    for pkg in data.get("package", []):
        source = pkg.get("source", {})
        if "registry" in source and "version" in pkg:
            out.append((pkg["name"], pkg["version"]))
    return sorted(out)


def main() -> int:
    locked = pins()
    queries = [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in locked]
    body = json.dumps({"queries": queries}).encode()
    req = urllib.request.Request(OSV, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed https endpoint
        results = json.load(resp)["results"]
    hits = [(locked[i], r["vulns"]) for i, r in enumerate(results) if r.get("vulns")]
    print(f"osv_audit: {len(locked)} locked packages, {len(hits)} with known advisories")
    for (name, version), vulns in hits:
        print(f"  {name}=={version}: {', '.join(v['id'] for v in vulns)}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
