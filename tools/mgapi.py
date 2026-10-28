"""Shared by the provisioning tools: a signed-in API session and the steps they repeat
(find or create a project, save and sync a connector, upload a document, follow a run,
issue a project API key to a client profile). Nothing here prints a credential."""

import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Proxies such as Cloudflare refuse the default "Python-urllib" agent: name ourselves.
USER_AGENT = "mindgrid-provision/0.1"
RUNNABLE = {"provisional", "active"}
# Where each playbook reports how many rows it kept.
COUNT_KEYS = ("candidate_count", "ranked_count", "count", "matched")


class Client:
    """A signed-in browser-like session (cookie + CSRF header) against the API."""

    def __init__(self, server: str) -> None:
        if not server.startswith(("https://", "http://")):
            raise SystemExit("--server must be an http(s) URL")
        self.server = server.rstrip("/")
        self.base = self.server + "/v1/"
        self.cookies: dict[str, str] = {}

    def call(
        self,
        method: str,
        path: str,
        body: object = None,
        form: bytes | None = None,
        content_type: str = "application/json",
    ) -> Any:
        headers = {"origin": self.server, "user-agent": USER_AGENT}
        if self.cookies:
            headers["cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            headers["x-csrf-token"] = self.cookies.get("__Host-mg_csrf", "")
        data = form if form is not None else (None if body is None else json.dumps(body).encode())
        if data is not None:
            headers["content-type"] = content_type
        req = urllib.request.Request(  # noqa: S310 - http(s) only, checked in __init__
            self.base + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as res:  # noqa: S310 - as above
                for cookie in res.headers.get_all("set-cookie") or []:
                    key, value = cookie.split(";", 1)[0].split("=", 1)
                    self.cookies[key] = value
                raw = res.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:300]
            raise SystemExit(f"{method} {path}: HTTP {err.code} {detail}") from None

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        found: dict[str, Any] = self.call(
            "POST", "auth/sign-in", {"email": email, "password": password}
        )
        return found


def secret_from_keychain(item: str) -> str:
    """A macOS Keychain password, named SERVICE/ACCOUNT."""
    service, _, account = item.partition("/")
    out = subprocess.run(  # noqa: S603 - fixed program, arguments passed as a list
        ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise SystemExit(f"Keychain item {service}/{account} not found")
    return out.stdout.strip()


def ensure_project(api: Client, slug: str, name: str, description: str) -> str:
    for p in api.call("GET", "projects"):
        if p["slug"] == slug:
            print(f"project      {name} (exists)")
            return str(p["id"])
    made = api.call("POST", "projects", {"slug": slug, "name": name, "description": description})
    print(f"project      {name} (created)")
    return str(made["id"])


def save_connector(
    api: Client, pid: str, name: str, spec: dict[str, Any], every_minutes: int | None
) -> None:
    body = {"spec": spec, "every_minutes": every_minutes}
    api.call("PUT", f"projects/{pid}/connectors/{name}", body)
    print(f"connector    {name}: {len(spec['resources'])} dataset(s), every {every_minutes} min")


def sync(api: Client, pid: str, name: str, wait_minutes: int) -> None:
    """Queue a sync of one connector and wait for the worker to finish it."""

    def current() -> dict[str, Any]:
        found: dict[str, Any] = next(
            c for c in api.call("GET", f"projects/{pid}/connectors") if c["name"] == name
        )
        return found

    before = current()
    api.call("POST", f"connectors/{before['id']}/sync")
    print(f"sync         {name}: queued; waiting for the worker", flush=True)
    deadline = time.monotonic() + wait_minutes * 60
    while time.monotonic() < deadline:
        time.sleep(10)
        now = current()
        if now["last_run_at"] != before["last_run_at"] and now["last_status"] in {"ok", "failed"}:
            note = now["last_error"] or ", ".join(now["last_changed"]) or "no change"
            print(f"sync         {name}: {now['last_status']}: {note}")
            if now["last_status"] != "ok":
                raise SystemExit(f"the sync of {name} failed; fix it and run again")
            return
    raise SystemExit("the sync did not finish in time (is a worker running?)")


def ensure_category(api: Client, pid: str, slug: str, name: str, description: str) -> str:
    for c in api.call("GET", f"projects/{pid}/categories"):
        if c["slug"] == slug:
            return str(c["id"])
    body = {"slug": slug, "name": name, "description": description, "restricted": False}
    return str(api.call("POST", f"projects/{pid}/categories", body)["id"])


@dataclass(frozen=True, slots=True)
class Upload:
    title: str  # also how a later run recognises the document
    filename: str
    data: bytes
    media_type: str = "text/markdown"


def upload_document(api: Client, category_id: str, doc: Upload) -> bool:
    """Upload one document unless a document with this title is already there."""
    title = doc.title
    if any(d["title"] == title for d in api.call("GET", f"categories/{category_id}/documents")):
        return False
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{doc.filename}"\r\nContent-Type: {doc.media_type}\r\n\r\n'.encode(),
        doc.data,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    api.call(
        "POST",
        f"categories/{category_id}/documents",
        form=b"".join(parts),
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    return True


def run_playbook(
    api: Client, pid: str, playbook: dict[str, Any], params: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    """Start a run of the newest runnable version and follow it until it ends."""
    version = max(
        (v["version"] for v in playbook["versions"] if v["status"] in RUNNABLE), default=None
    )
    if version is None:
        return {"status": "skipped", "error": "no runnable version", "outputs": {}}
    body = {
        "playbook": playbook["id"],
        "version": version,
        "params": params,
        "inputs": inputs,
        "wait_seconds": 60,
    }
    run: dict[str, Any] = api.call("POST", f"projects/{pid}/runs", body)
    deadline = time.monotonic() + 20 * 60  # large screens outlast one wait
    while run["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(10)
        run = api.call("GET", f"runs/{run['id']}")
    return run


def shown_path(path: Path) -> str:
    """A path as printed: under the home folder it starts with ~ (logs never hold it)."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def numeric_sample(api: Client, pid: str, dataset: str) -> tuple[str, list[dict[str, Any]]]:
    """The first numeric column of a dataset and 50 of its rows (for the generic screens)."""
    page = api.call("GET", f"projects/{pid}/datasets/{dataset}/rows?limit=50")
    for column in page["columns"]:
        if all(isinstance(r.get(column), int | float) for r in page["items"] if r.get(column)):
            return column, page["items"]
    raise SystemExit(f"no numeric column in {dataset}")


def generic_runs(
    api: Client, pid: str, dataset: str
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Parameters and inputs for the built-in screens (core.*), from one dataset."""
    column, sample = numeric_sample(api, pid, dataset)
    screen = {"filter_column": column, "rank_by": column, "minimum": 0}
    return {
        "core.dataset-screen": (screen, {"data": dataset}),
        "core.table-screen": (screen, {"rows": sample}),
    }


def result_count(run: dict[str, Any]) -> object:
    outputs = run.get("outputs") or {}
    return next((outputs[k] for k in COUNT_KEYS if k in outputs), "")


@dataclass(frozen=True, slots=True)
class KeyRequest:
    owner_id: str
    project_id: str
    name: str  # also how a later run recognises the key
    profile: str  # client profile (and key file) name
    days: int


def issue_project_key(api: Client, want: KeyRequest) -> dict[str, Any] | None:
    """A read+run key limited to one project, saved as a client profile (key file mode 600).
    Returns the issued key (with its private key, kept in memory only), or None if a key
    with this name already exists."""
    name, profile = want.name, want.profile
    from mindgrid.interfaces.remote import profiles  # noqa: PLC0415 - needs the backend venv

    if any(k["name"] == name and not k["revoked_at"] for k in api.call("GET", "admin/api-keys")):
        print(f"api key      {name} (exists; kept)")
        return None
    body = {
        "owner_user_id": want.owner_id,
        "name": name,
        "scopes": ["read", "run"],
        "project_ids": [want.project_id],
        "days": want.days,
    }
    issued: dict[str, Any] = api.call("POST", "admin/api-keys", body)
    key_file = profiles.remote_config.config_dir() / f"{profile}.pem"
    profiles.write_private(key_file, issued["private_key_pem"])
    profiles.save(
        profiles.Profile(
            name=profile, server=api.server, key_id=issued["key"]["key_id"], key_file=str(key_file)
        )
    )
    print(f"api key      {issued['key']['key_id']} -> profile '{profile}' (file mode 600)")
    return issued
