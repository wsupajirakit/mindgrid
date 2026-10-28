"""Settings per scope: /v1/{scope}/{id}/settings, where scope is admin (system), me,
projects or categories. GET lists every setting declared for that scope with its
effective value and where it comes from; PUT sets one; DELETE falls back."""

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.core.settings_registry import Scope
from mindgrid.platform.settings import service as settings

from . import scopes
from .deps import CurrentPrincipal, Tx

router = APIRouter(tags=["settings"])


class SettingOut(BaseModel):
    key: str
    value: Any
    source: str  # the scope the value comes from, or "default"
    doc: str
    schema_: dict[str, Any] = Field(alias="schema", serialization_alias="schema")


class SettingBody(BaseModel):
    value: Any


async def _list(tx: Tx, principal: CurrentPrincipal, at: scopes.At) -> list[SettingOut]:
    await scopes.check(tx, principal, at.scope, at.id, write=False)
    chain = await scopes.chain_for(tx, principal, at.scope, at.id)
    found = await settings.resolve_all(tx, at.scope, chain)
    return [
        SettingOut(
            key=r.key,
            value=r.value,
            source=r.source.value if r.source else "default",
            doc=r.doc,
            schema=r.schema,
        )
        for r in found
    ]


async def _put(tx: Tx, principal: CurrentPrincipal, at: scopes.At, key: str, value: object) -> None:
    await scopes.check(tx, principal, at.scope, at.id, write=True)
    await settings.put(tx, at.scope, at.id, key, value)


async def _clear(tx: Tx, principal: CurrentPrincipal, at: scopes.At, key: str) -> None:
    await scopes.check(tx, principal, at.scope, at.id, write=True)
    await settings.clear(tx, at.scope, at.id, key)


@router.get("/admin/settings")
async def system_settings(tx: Tx, p: CurrentPrincipal) -> list[SettingOut]:
    return await _list(tx, p, scopes.At(Scope.SYSTEM, None))


@router.put("/admin/settings/{key}", status_code=204)
async def put_system(key: str, body: SettingBody, tx: Tx, p: CurrentPrincipal) -> None:
    await _put(tx, p, scopes.At(Scope.SYSTEM, None), key, body.value)


@router.get("/me/settings")
async def my_settings(tx: Tx, p: CurrentPrincipal) -> list[SettingOut]:
    return await _list(tx, p, scopes.At(Scope.USER, p.user_id))


@router.put("/me/settings/{key}", status_code=204)
async def put_mine(key: str, body: SettingBody, tx: Tx, p: CurrentPrincipal) -> None:
    await _put(tx, p, scopes.At(Scope.USER, p.user_id), key, body.value)


@router.delete("/me/settings/{key}", status_code=204)
async def clear_mine(key: str, tx: Tx, p: CurrentPrincipal) -> None:
    await _clear(tx, p, scopes.At(Scope.USER, p.user_id), key)


@router.get("/projects/{project_id}/settings")
async def project_settings(project_id: uuid.UUID, tx: Tx, p: CurrentPrincipal) -> list[SettingOut]:
    return await _list(tx, p, scopes.At(Scope.PROJECT, project_id))


@router.put("/projects/{project_id}/settings/{key}", status_code=204)
async def put_project(
    project_id: uuid.UUID, key: str, body: SettingBody, tx: Tx, p: CurrentPrincipal
) -> None:
    await _put(tx, p, scopes.At(Scope.PROJECT, project_id), key, body.value)


@router.get("/categories/{category_id}/settings")
async def category_settings(
    category_id: uuid.UUID, tx: Tx, p: CurrentPrincipal
) -> list[SettingOut]:
    return await _list(tx, p, scopes.At(Scope.CATEGORY, category_id))


@router.put("/categories/{category_id}/settings/{key}", status_code=204)
async def put_category(
    category_id: uuid.UUID, key: str, body: SettingBody, tx: Tx, p: CurrentPrincipal
) -> None:
    await _put(tx, p, scopes.At(Scope.CATEGORY, category_id), key, body.value)
