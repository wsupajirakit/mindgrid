"""The connector spec (stored per project as JSON). Secrets are never in the spec: `auth`
names a project secret, read server-side when the connector runs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mindgrid.datasets.models import NAME


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Auth(_Strict):
    type: Literal["none", "bearer", "header", "query", "basic"] = "none"
    secret: str = Field(
        default="", description="Project secret holding the token (or user:password)."
    )
    name: str = Field(
        default="", description="Header or query parameter name (header / query auth)."
    )


class Resource(_Strict):
    dataset: str = Field(pattern=NAME, description="Dataset this resource fills.")
    path: str = Field(pattern=r"^/", description="Path under the base URL.")
    query: dict[str, str] = Field(default_factory=dict[str, str])
    format: Literal["csv", "json", "ndjson"] = "csv"
    records_path: str = Field(default="", description="JSON only: dot path to the list of records.")
    title: str = ""


class ConnectorSpec(_Strict):
    base_url: str = Field(pattern=r"^https?://[^\s/]+", description="Scheme and host.")
    auth: Auth = Field(default_factory=Auth)
    resources: list[Resource] = Field(min_length=1, max_length=50)
    timeout_seconds: float = Field(120, ge=5, le=600)
