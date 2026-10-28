"""The playbook spec (JSON; its JSON Schema is published at /v1/playbooks/schema).

Values in `steps[].with` and `outputs` may reference `$inputs.<name>`, `$params.<name>` or
`$steps.<step id>.<field>` (also inside lists and objects); `$$` starts a literal `$`."""

import enum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PLAYBOOK_ID = r"^[a-z][a-z0-9_]*\.[a-z0-9][a-z0-9_-]{0,63}$"
STEP_ID = r"^[a-z][a-z0-9_]{0,31}$"
ValueType = Literal["number", "integer", "string", "boolean", "array", "object"]
InputType = ValueType | Literal["dataset"]  # a dataset name: the run pins its version


class Status(enum.StrEnum):
    DRAFT = "draft"  # being written: runs only on request, never listed as usable
    PROVISIONAL = "provisional"  # usable, evidence still thin: results carry the flag
    ACTIVE = "active"
    PAUSED = "paused"  # measured without an edge (or broken): kept, cannot run
    RETIRED = "retired"  # replaced: old runs stay readable, new runs refused


RUNNABLE = {Status.DRAFT, Status.PROVISIONAL, Status.ACTIVE}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ParamSpec(_Strict):
    type: ValueType
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[Any] | None = None
    doc: str = ""


class InputSpec(_Strict):
    type: InputType
    required: bool = True
    default: Any = None  # used when the run does not give this input
    doc: str = ""


class Translation(_Strict):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=2000)


LOCALE = r"^[a-z]{2}$"


class Step(_Strict):
    id: str = Field(pattern=STEP_ID)
    fn: str
    with_: dict[str, Any] = Field(default_factory=dict[str, Any], alias="with")


class PlaybookSpec(_Strict):
    id: str = Field(pattern=PLAYBOOK_ID)
    version: int = Field(ge=1)
    status: Status
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""
    inputs: dict[str, InputSpec] = Field(default_factory=dict[str, InputSpec])
    params: dict[str, ParamSpec] = Field(default_factory=dict[str, ParamSpec])
    steps: list[Step] = Field(min_length=1, max_length=100)
    outputs: dict[str, Any] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list[str])  # knowledge refs backing it
    # Title and summary in other languages (keyed by locale, e.g. "th"); English is the base.
    translations: dict[str, Translation] = Field(default_factory=dict[str, Translation])

    @model_validator(mode="after")
    def _unique_steps(self) -> PlaybookSpec:
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        for locale in self.translations:
            if not re.fullmatch(LOCALE, locale):
                raise ValueError(f"translation locale {locale!r} must be two lowercase letters")
        for name in [*self.inputs, *self.params]:
            if not re.fullmatch(STEP_ID, name):
                raise ValueError(f"input/param name {name!r} must be snake_case")
        return self
