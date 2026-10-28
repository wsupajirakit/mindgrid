"""Knowledge calls shared by the CLI and the MCP server (one behaviour for both): find a
project by slug or id, fetch a Context Pack, ask for a server-written answer, check an
answer's citations."""

import uuid
from typing import Any

from .client import RemoteClient, RemoteError


async def projects(client: RemoteClient) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = await client.call("GET", "/v1/projects")
    return [{k: p[k] for k in ("id", "slug", "name", "description")} for p in found]


async def project_id(client: RemoteClient, ref: str) -> str:
    """A project id from an id or a slug (the slug must match exactly one visible project)."""
    try:
        return str(uuid.UUID(ref))
    except ValueError:
        pass
    matches = [p["id"] for p in await projects(client) if p["slug"] == ref]
    if len(matches) != 1:
        raise RemoteError(404, "project.not_found", f"no project with slug {ref!r}")
    return str(matches[0])


async def categories(client: RemoteClient, project: str) -> list[dict[str, Any]]:
    pid = await project_id(client, project)
    found: list[dict[str, Any]] = await client.call("GET", f"/v1/projects/{pid}/categories")
    return [{k: c[k] for k in ("id", "slug", "name", "restricted")} for c in found]


def _body(query: str, categories: list[str] | None, k: int) -> dict[str, Any]:
    return {"query": query, "categories": categories or [], "k": k}


async def pack(
    client: RemoteClient, project: str, query: str, categories: list[str] | None = None, k: int = 0
) -> dict[str, Any]:
    pid = await project_id(client, project)
    return await client.call(
        "POST", f"/v1/projects/{pid}/context-pack", _body(query, categories, k)
    )


async def answer(
    client: RemoteClient,
    project: str,
    query: str,
    llm: str | None = None,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    pid = await project_id(client, project)
    body = {**_body(query, categories, 0), "llm": llm}
    return await client.call("POST", f"/v1/projects/{pid}/answer", body)


async def verify(client: RemoteClient, text: str, refs: list[str]) -> dict[str, Any]:
    return await client.call("POST", "/v1/citations/verify", {"answer": text, "refs": refs})


async def report(client: RemoteClient, report_body: dict[str, Any]) -> dict[str, Any]:
    """Keep an answer written on this side with its logged question (checked server-side).
    `report_body`: recall_id, answer, refs, writer, channel (mcp | cli | api)."""
    return await client.call("POST", "/v1/answers", report_body)


def pack_text(found: dict[str, Any]) -> str:
    """The pack as plain text for a model: rules, then the delimited passages."""
    notes = [f"note: {name} search skipped ({why})" for name, why in found["skipped"].items()]
    passages = found["rendered"] or "(no passage matched; say the knowledge base has nothing)"
    recall_id = found.get("recall_id")
    tail = [f"recall_id: {recall_id}"] if recall_id else []
    return "\n".join([f"Rules: {found['rules']}", *notes, "", passages, *tail])


async def playbooks(client: RemoteClient, project: str) -> list[dict[str, Any]]:
    pid = await project_id(client, project)
    return await client.call("GET", "/v1/playbooks", query={"project_id": pid})


async def run_playbook(
    client: RemoteClient, project: str, request: dict[str, Any]
) -> dict[str, Any]:
    """`request` = {"playbook", "params", "inputs", "wait_seconds"} as the runs API takes it."""
    pid = await project_id(client, project)
    body = {"wait_seconds": 30, **request}
    return await client.call("POST", f"/v1/projects/{pid}/runs", body)
