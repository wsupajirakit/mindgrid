"""Write docs/postman/api.postman_collection.json: a Postman collection (v2.1) that calls
the API with a project API key. A collection script signs every request (RFC 9421,
Ed25519 through the vendored TweetNaCl) and fetches the access token on its own, so a user
imports the collection and an environment (base_url, project_slug, key_id, private_key;
tools/demo_projects.py writes them) and presses Send.

  backend/.venv/bin/python tools/postman_collection.py [--check]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "tools" / "postman"
OUT = ROOT / "docs" / "postman" / "api.postman_collection.json"
# TweetNaCl 1.0.3 (public domain), as published on npm; the generator refuses anything else.
NACL_SHA256 = "973cc5733cc7432e30ee4682098f413094f494bccf76a567c23908c5035ddbbc"
# The two places the browser/Node build reaches for globals Postman's sandbox lacks; the
# random generator they set up is not needed to sign.
NACL_PATCHES = (
    (
        '"undefined"!=typeof module&&module.exports?module.exports:self.nacl=self.nacl||{}',
        "MG_NACL",
    ),
    # The build writes `else"undefined"...`: the space keeps `else false` valid.
    ('"undefined"!=typeof require&&(o=require("crypto"))', " false"),
)
JSON_HEADER = [{"key": "content-type", "value": "application/json"}]


def _nacl() -> str:
    code = (HERE / "vendor" / "nacl.min.js").read_text()
    if hashlib.sha256(code.encode()).hexdigest() != NACL_SHA256:
        raise SystemExit("tools/postman/vendor/nacl.min.js is not TweetNaCl 1.0.3")
    for old, new in NACL_PATCHES:
        if code.count(old) != 1:
            raise SystemExit(f"TweetNaCl patch point not found: {old[:40]}")
        code = code.replace(old, new)
    return "var MG_NACL = {};\n" + code + "\n"


def _script(kind: str, lines: str) -> list[dict[str, Any]]:
    return [{"listen": kind, "script": {"type": "text/javascript", "exec": lines.splitlines()}}]


def _expect(*statuses: int, then: str = "") -> list[dict[str, Any]]:
    codes = ", ".join(str(s) for s in statuses)
    return _script(
        "test",
        f"pm.test('status is {codes}', () => "
        f"pm.expect([{codes}]).to.include(pm.response.code));\n{then}",
    )


def _described(item: dict[str, Any], doc: str) -> dict[str, Any]:
    item["request"]["description"] = doc
    return item


def _request(
    name: str,
    method: str,
    path: str,
    *,
    body: object = None,
    tests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = path.split("?", 1)
    url: dict[str, Any] = {
        "raw": "{{base_url}}" + path,
        "host": ["{{base_url}}"],
        "path": [p for p in raw[0].split("/") if p],
    }
    if len(raw) == 2:
        url["query"] = [
            dict(zip(("key", "value"), q.split("=", 1), strict=True)) for q in raw[1].split("&")
        ]
    request: dict[str, Any] = {"method": method, "header": [], "url": url}
    if body is not None:
        request["header"] = JSON_HEADER
        text = body if isinstance(body, str) else json.dumps(body, indent=2)
        request["body"] = {"mode": "raw", "raw": text, "options": {"raw": {"language": "json"}}}
    return {"name": name, "request": request, "event": tests or _expect(200)}


PICK_PROJECT = """const slug = pm.environment.get('project_slug');
const found = pm.response.json().find((p) => p.slug === slug);
pm.test('the project of this key is listed', () => pm.expect(found, slug).to.exist);
if (found) pm.collectionVariables.set('project_id', found.id);"""
PICK_PLAYBOOK = """const on = pm.response.json()
  .filter((p) => p.enabled && !p.id.startsWith('core.'));
pm.test('the project has playbooks switched on', () => pm.expect(on.length).to.be.above(0));
if (on.length) {
  const p = on[0];
  const runnable = p.versions.filter((v) => ['provisional', 'active'].includes(v.status));
  pm.collectionVariables.set('playbook_id', p.id);
  const newest = Math.max(...runnable.map((v) => v.version));
  pm.collectionVariables.set('playbook_version', String(newest));
}"""
PICK_DATASET = """const sets = pm.response.json();
pm.test('the project has data', () => pm.expect(sets.length).to.be.above(0));
if (sets.length) pm.collectionVariables.set('dataset', sets[0].name);"""
KEEP_RUN = """const run = pm.response.json();
pm.collectionVariables.set('run_id', run.id);
pm.test('the run finished or is on its way', () =>
  pm.expect(['done', 'queued', 'running']).to.include(run.status));"""
# Raw text: the version placeholder must stay an unquoted JSON number.
RUN_BODY = """{
  "playbook": "{{playbook_id}}",
  "version": {{playbook_version}},
  "params": {},
  "inputs": {},
  "wait_seconds": 30
}"""
HAS_HITS = """pm.test('hits come back', () =>
  pm.expect(pm.response.json().hits).to.be.an('array'));"""
HAS_PASSAGES = """pm.test('passages come back', () =>
  pm.expect(pm.response.json().passages).to.be.an('array'));"""


def collection() -> dict[str, Any]:
    pid = "/v1/projects/{{project_id}}"
    folders = [
        (
            "Projects",
            [
                _request(
                    "List projects (finds the key's project)",
                    "GET",
                    "/v1/projects",
                    tests=_expect(200, then=PICK_PROJECT),
                ),
                _request("Get the project", "GET", pid),
            ],
        ),
        (
            "Knowledge",
            [
                _request("Categories", "GET", f"{pid}/categories"),
                _described(
                    _request(
                        "Recall passages",
                        "POST",
                        f"{pid}/recall",
                        body={"query": "{{question}}", "k": 5},
                        tests=_expect(200, then=HAS_HITS),
                    ),
                    "Hybrid search over the project's documents.",
                ),
                _described(
                    _request(
                        "Context pack",
                        "POST",
                        f"{pid}/context-pack",
                        body={"query": "{{question}}", "k": 5},
                        tests=_expect(200, then=HAS_PASSAGES),
                    ),
                    "Passages plus the rules to answer only from them (for any LLM).",
                ),
            ],
        ),
        (
            "Playbooks",
            [
                _request(
                    "Playbooks of the project",
                    "GET",
                    "/v1/playbooks?project_id={{project_id}}",
                    tests=_expect(200, then=PICK_PLAYBOOK),
                ),
                _request(
                    "Run a playbook",
                    "POST",
                    f"{pid}/runs",
                    body=RUN_BODY,
                    tests=_expect(201, then=KEEP_RUN),
                ),
                _request("Get the run", "GET", "/v1/runs/{{run_id}}"),
            ],
        ),
        (
            "Data",
            [
                _request(
                    "Datasets", "GET", f"{pid}/datasets", tests=_expect(200, then=PICK_DATASET)
                ),
                _request("Dataset rows", "GET", f"{pid}/datasets/{{{{dataset}}}}/rows?limit=20"),
            ],
        ),
    ]
    return {
        "info": {
            "name": "API (signed with a project key)",
            "description": __doc__.split("\n\n", 1)[0],
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "event": _script("prerequest", _nacl() + (HERE / "sign.js").read_text()),
        "variable": [
            {"key": k, "value": v}
            for k, v in (
                ("question", "What does this project measure?"),
                ("project_id", ""),
                ("playbook_id", ""),
                ("playbook_version", "1"),
                ("run_id", ""),
                ("dataset", ""),
            )
        ],
        "item": [{"name": name, "item": items} for name, items in folders],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="Fail when the file is stale")
    text = json.dumps(collection(), indent=2, ensure_ascii=False) + "\n"
    if parser.parse_args().check:
        if not OUT.exists() or OUT.read_text() != text:
            raise SystemExit(f"{OUT.relative_to(ROOT)} is stale: run tools/postman_collection.py")
        print(f"{OUT.relative_to(ROOT)}: current")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
