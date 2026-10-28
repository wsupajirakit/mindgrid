"""Validated inputs for creating projects and categories (shared by services and API)."""

from pydantic import BaseModel, Field

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"


class ProjectInput(BaseModel):
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class CategoryInput(BaseModel):
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    restricted: bool = False
