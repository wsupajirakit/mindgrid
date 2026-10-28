"""Commands that call the engine's server with an API key (bash, scripts, a local LLM):
`login`, `projects`, `categories`, `pack`, `ask`, `verify`. `--json` prints the raw
response; otherwise a readable form. Exit code 1 = the server refused the call."""

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from mindgrid.interfaces.remote import knowledge, profiles
from mindgrid.interfaces.remote.client import RemoteClient, RemoteError

Json = Annotated[bool, typer.Option("--json", help="Print the raw JSON response.")]
ProfileName = Annotated[str, typer.Option(help="Client profile (default: MINDGRID_PROFILE).")]
Project = Annotated[str, typer.Option("--project", "-p", help="Project slug or id.")]


def _run(profile: str, work: Callable[[RemoteClient], Awaitable[Any]]) -> Any:
    async def go() -> Any:
        async with RemoteClient(profiles.get(profile)) as client:
            return await work(client)

    try:
        return asyncio.run(go())
    except (RemoteError, LookupError, PermissionError) as err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(1) from None


def _print(data: Any, as_json: bool, text: Callable[[Any], str]) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2) if as_json else text(data))


def login(
    server: Annotated[str, typer.Option(help="Server base URL.")],
    key_id: Annotated[str, typer.Option(help="API key id (mgk_...).")],
    key_file: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Private key (PEM, chmod 600).")
    ],
    profile: Annotated[str, typer.Option(help="Profile name.")] = "default",
) -> None:
    """Save a client profile and check it against the server."""
    entry = profiles.Profile(
        name=profile, server=server, key_id=key_id, key_file=str(key_file.expanduser().resolve())
    )
    entry.credentials()  # refuses a key file readable by others
    profiles.save(entry)
    found = _run(profile, knowledge.projects)
    typer.echo(f"profile {profile!r} saved; {len(found)} project(s) visible")


def projects(as_json: Json = False, profile: ProfileName = "") -> None:
    """Projects this key can see."""
    found = _run(profile, knowledge.projects)
    _print(found, as_json, lambda rows: "\n".join(f"{p['slug']}\t{p['name']}" for p in rows))


def categories(project: Project, as_json: Json = False, profile: ProfileName = "") -> None:
    """Categories of a project."""
    found = _run(profile, lambda c: knowledge.categories(c, project))
    _print(found, as_json, lambda rows: "\n".join(f"{x['slug']}\t{x['name']}" for x in rows))


def pack(
    query: Annotated[str, typer.Argument(help="The question.")],
    project: Project,
    category: Annotated[list[str] | None, typer.Option(help="Category id (repeatable).")] = None,
    k: Annotated[int, typer.Option(help="Passages (0 = server default).")] = 0,
    as_json: Json = False,
    profile: ProfileName = "",
) -> None:
    """The Context Pack for a question: answer from it, citing [P1], [P2], ..."""
    found = _run(profile, lambda c: knowledge.pack(c, project, query, category, k))
    _print(found, as_json, knowledge.pack_text)


def ask(
    query: Annotated[str, typer.Argument(help="The question.")],
    project: Project,
    llm: Annotated[
        str | None, typer.Option(help="none | local | gemini (default: project).")
    ] = None,
    as_json: Json = False,
    profile: ProfileName = "",
) -> None:
    """A server-written answer with its citation check."""
    done = _run(profile, lambda c: knowledge.answer(c, project, query, llm))

    def text(d: dict[str, Any]) -> str:
        if d["answer"] is None:
            return knowledge.pack_text(d["pack"])
        check: dict[str, Any] = d["check"] or {}
        verdict = "citations ok" if check.get("ok") else f"check citations: {check}"
        return f"{d['answer']}\n\n[{d['writer']} · {verdict}]"

    _print(done, as_json, text)


def verify(
    refs: Annotated[str, typer.Option(help="The pack's references, e.g. P1,P2,P3.")],
    as_json: Json = False,
    profile: ProfileName = "",
) -> None:
    """Check an answer (read from stdin) against a pack's references."""
    answer_text = sys.stdin.read()
    wanted = [r.strip() for r in refs.split(",") if r.strip()]
    done = _run(profile, lambda c: knowledge.verify(c, answer_text, wanted))
    _print(done, as_json, lambda d: "ok" if d["ok"] else json.dumps(d, ensure_ascii=False))
    if not done["ok"]:
        raise typer.Exit(2)


def playbooks(project: Project, as_json: Json = False, profile: ProfileName = "") -> None:
    """Playbooks usable in a project, with their versions and status."""
    found = _run(profile, lambda c: knowledge.playbooks(c, project))

    def text(rows: list[dict[str, Any]]) -> str:
        def line(p: dict[str, Any]) -> str:
            versions = ", ".join(f"v{v['version']} {v['status']}" for v in p["versions"])
            state = "on" if p["enabled"] else "off"
            return f"{p['id']}\t{state}\t{versions}\t{p['title']}"

        return "\n".join(line(p) for p in rows)

    _print(found, as_json, text)


def run(
    playbook: Annotated[str, typer.Argument(help="Playbook id.")],
    project: Project,
    param: Annotated[
        list[str] | None, typer.Option(help="name=value (JSON value), repeatable.")
    ] = None,
    inputs: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="JSON file with the inputs.")
    ] = None,
    wait: Annotated[float, typer.Option(help="Seconds to wait for the result.")] = 30,
    as_json: Json = False,
    profile: ProfileName = "",
) -> None:
    """Run a playbook and print its outputs (exit 3 when the run failed)."""
    values: dict[str, Any] = {}
    for item in param or []:
        name, _, raw = item.partition("=")
        try:
            values[name] = json.loads(raw)
        except json.JSONDecodeError:
            values[name] = raw
    given: dict[str, Any] = json.loads(inputs.read_text(encoding="utf-8")) if inputs else {}
    request = {"playbook": playbook, "params": values, "inputs": given, "wait_seconds": wait}
    done = _run(profile, lambda c: knowledge.run_playbook(c, project, request))
    _print(
        done,
        as_json,
        lambda d: json.dumps(
            {"status": d["status"], "outputs": d["outputs"], "error": d["error"]},
            ensure_ascii=False,
            indent=2,
        ),
    )
    if done["status"] == "failed":
        raise typer.Exit(3)


def register(app: typer.Typer) -> None:
    for command in (login, projects, categories, pack, ask, verify, playbooks, run):
        app.command()(command)
