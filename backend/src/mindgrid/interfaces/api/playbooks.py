"""/v1/functions, /v1/playbooks: the catalog, published specs and their JSON Schema,
custom specs (superadmin) and overrides per system or project."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from mindgrid.core.settings_registry import Scope
from mindgrid.functions import registry
from mindgrid.playbooks import assignments, catalog, overrides, translations
from mindgrid.playbooks.spec import PlaybookSpec, Translation

from .deps import CurrentPrincipal, SuperadminPrincipal, Tx

router = APIRouter(tags=["playbooks"])


class VersionOut(BaseModel):
    version: int
    status: str


class PlaybookOut(BaseModel):
    id: str
    title: str
    summary: str
    versions: list[VersionOut]
    enabled: bool
    pinned_version: int | None
    params: dict[str, Any] = Field(description="Overridden parameters in force here.")
    inputs: list[str] = Field(default_factory=list[str], description="Inputs the newest takes.")
    param_names: list[str] = Field(default_factory=list[str], description="Its parameters.")
    functions: list[str] = Field(default_factory=list[str], description="Function per step.")
    translations: dict[str, Translation] = Field(
        default_factory=dict[str, Translation],
        description="Title and summary per other language (shipped text, or a saved one).",
    )


class OverrideIn(BaseModel):
    enabled: bool = True
    version: int | None = Field(None, ge=1, description="Pin a version (null = newest).")
    params: dict[str, Any] = Field(default_factory=dict[str, Any])


@router.get("/functions")
def functions(principal: CurrentPrincipal) -> list[dict[str, Any]]:
    del principal  # signed-in callers only
    return registry.catalog()


@router.get("/playbooks/schema")
def spec_schema(principal: CurrentPrincipal) -> dict[str, Any]:
    del principal
    return PlaybookSpec.model_json_schema(by_alias=True)


@router.get("/playbooks")
async def list_playbooks(
    tx: Tx, project_id: Annotated[uuid.UUID | None, Query()] = None
) -> list[PlaybookOut]:
    return [PlaybookOut.model_validate(s) for s in await catalog.summaries(tx, project_id)]


@router.get("/playbooks/{playbook_id}/versions/{version}")
async def get_spec(playbook_id: str, version: int, tx: Tx) -> dict[str, Any]:
    spec = catalog.pick(await catalog.all_specs(tx), playbook_id, version, None)
    return spec.model_dump(mode="json", by_alias=True)


@router.post("/admin/playbooks", status_code=201)
async def add_custom(spec: PlaybookSpec, tx: Tx, principal: SuperadminPrincipal) -> dict[str, str]:
    del principal
    await catalog.add_custom(tx, spec)
    return {"id": spec.id, "version": str(spec.version)}


def _change(body: OverrideIn) -> overrides.Change:
    return overrides.Change(body.enabled, body.version, body.params)


@router.put("/projects/{project_id}/playbooks/{playbook_id}", status_code=204)
async def put_project_override(
    project_id: uuid.UUID, playbook_id: str, body: OverrideIn, tx: Tx, principal: CurrentPrincipal
) -> None:
    target = (Scope.PROJECT, project_id)
    await overrides.put(tx, target, playbook_id, _change(body), principal.superadmin)


@router.delete("/projects/{project_id}/playbooks/{playbook_id}", status_code=204)
async def clear_project_override(
    project_id: uuid.UUID, playbook_id: str, tx: Tx, principal: CurrentPrincipal
) -> None:
    await overrides.clear(tx, (Scope.PROJECT, project_id), playbook_id, principal.superadmin)


@router.put("/admin/playbooks/{playbook_id}/override", status_code=204)
async def put_system_override(
    playbook_id: str, body: OverrideIn, tx: Tx, principal: SuperadminPrincipal
) -> None:
    await overrides.put(tx, (Scope.SYSTEM, None), playbook_id, _change(body), principal.superadmin)


class ProjectChoiceOut(BaseModel):
    project_id: uuid.UUID
    name: str
    enabled: bool = Field(description="Runs in this project today.")
    own_choice: bool = Field(description="The project made its own choice (it wins).")
    can_manage: bool = Field(description="The caller may change this project's choice.")


class AssignmentsOut(BaseModel):
    playbook_id: str
    all_projects: bool = Field(description="The system switch: on for every project.")
    projects: list[ProjectChoiceOut]


class AssignmentsIn(BaseModel):
    all_projects: bool | None = Field(
        default=None, description="Set the system switch (superadmin); omit to leave it."
    )
    projects: dict[uuid.UUID, bool] = Field(
        default_factory=dict[uuid.UUID, bool], description="Per project: on or off."
    )


def _assignments_out(a: assignments.Assignments) -> AssignmentsOut:
    return AssignmentsOut(
        playbook_id=a.playbook_id,
        all_projects=a.all_projects,
        projects=[
            ProjectChoiceOut(
                project_id=p.project_id,
                name=p.name,
                enabled=p.enabled,
                own_choice=p.own_choice,
                can_manage=p.can_manage,
            )
            for p in a.projects
        ],
    )


@router.get("/playbooks/{playbook_id}/assignments")
async def get_assignments(playbook_id: str, tx: Tx) -> AssignmentsOut:
    return _assignments_out(await assignments.of(tx, playbook_id))


@router.put("/playbooks/{playbook_id}/assignments")
async def put_assignments(
    playbook_id: str, body: AssignmentsIn, tx: Tx, principal: CurrentPrincipal
) -> AssignmentsOut:
    """Which projects may run the playbook; returns the result as stored."""
    await assignments.assign(
        tx, playbook_id, body.projects, body.all_projects, principal.superadmin
    )
    return _assignments_out(await assignments.of(tx, playbook_id))


@router.put("/admin/playbooks/{playbook_id}/translations/{locale}", status_code=204)
async def put_translation(
    playbook_id: str, locale: str, body: Translation, tx: Tx, principal: SuperadminPrincipal
) -> None:
    """The title and summary shown in `locale` (wins over the text the spec ships)."""
    del principal
    await translations.put(tx, await catalog.all_specs(tx), (playbook_id, locale), body)


@router.delete("/admin/playbooks/{playbook_id}/translations/{locale}", status_code=204)
async def clear_translation(
    playbook_id: str, locale: str, tx: Tx, principal: SuperadminPrincipal
) -> None:
    del principal
    await translations.clear(tx, playbook_id, locale)
