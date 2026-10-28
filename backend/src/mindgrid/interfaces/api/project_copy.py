"""/v1/admin/projects/{id}/copy (superadmin): copy chosen categories with their documents
and the playbook choices into another project. Each project keeps its own copy."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.knowledge.library import copying
from mindgrid.platform.tenancy import access
from mindgrid.playbooks import overrides

from .deps import SuperadminPrincipal, Tx

router = APIRouter(tags=["admin"])


class CopyIn(BaseModel):
    target_project_id: uuid.UUID
    category_ids: list[uuid.UUID] = Field(
        default_factory=list[uuid.UUID], description="Categories to copy, with documents."
    )
    playbooks: bool = Field(default=False, description="Also copy which playbooks are on.")


class CopyOut(BaseModel):
    categories: int
    documents: int
    playbooks: int


@router.post("/admin/projects/{project_id}/copy")
async def copy_project(
    project_id: uuid.UUID, body: CopyIn, tx: Tx, principal: SuperadminPrincipal
) -> CopyOut:
    await access.require_project_view(tx, project_id)
    await access.require_project_view(tx, body.target_project_id)
    copied = await copying.copy_categories(
        tx, project_id, body.target_project_id, body.category_ids
    )
    playbooks = 0
    if body.playbooks:
        playbooks = await overrides.copy_project(
            tx, project_id, body.target_project_id, principal.superadmin
        )
    return CopyOut(categories=copied.categories, documents=copied.documents, playbooks=playbooks)
