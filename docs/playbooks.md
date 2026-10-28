# Writing functions and playbooks

A **function** computes; a **playbook** chains functions into a versioned procedure with
parameters. Numbers always come from functions — a language model only reads the result.

## Functions

A function is pure: one validated arguments model in, one output model out, nothing else
read (no database, clock or environment), so a run can be replayed.

```python
from pydantic import Field

from mindgrid.functions.contracts import Args, Output
from mindgrid.functions.registry import function


class TopArgs(Args):  # unknown fields are refused
    rows: list[dict]
    n: int = Field(10, ge=1, le=10_000)  # every threshold is a bounded parameter


class Rows(Output):
    rows: list[dict]
    count: int


@function("mypack.table.top", "The first n rows.", TopArgs, Rows)
def top(a: TopArgs) -> Rows:
    return Rows(rows=a.rows[: a.n], count=min(len(a.rows), a.n))
```

A dataset input arrives as a `Frame` (the pinned version's original bytes, its metadata,
and columns parsed on first use). The catalog with JSON Schemas: `GET /v1/functions`.

## Playbooks

A playbook is a JSON spec (schema: `GET /v1/playbooks/schema`):

| Field | Meaning |
|--|--|
| `id`, `version` | `pack.name` and an integer; a published version never changes — add a new one |
| `status` | `draft` (runs only when asked for by version), `provisional` (usable, evidence thin), `active`, `paused` (kept, cannot run), `retired` |
| `inputs` | name → `{type, required, default, doc}`; type `dataset` takes a dataset name and the run pins its version |
| `params` | name → `{type, default, minimum, maximum, choices, doc}`; checked before a run starts |
| `steps` | `{id, fn, with}`; `with` values may reference `$inputs.<name>`, `$params.<name>` or `$steps.<id>.<field>` (also inside lists and objects); `$$` is a literal `$` |
| `outputs` | name → a reference; what the run keeps |
| `evidence` | knowledge references backing the playbook |

A spec is checked before it is accepted: every function exists, every reference points at
a declared input, parameter or an earlier step, every default respects its bounds.

## Where specs come from

- **Shipped:** JSON files in a package named by the `mindgrid.playbooks` entry point (the
  engine's built-ins, each pack's own).
- **Custom:** a superadmin posts a spec (*Playbooks* page or `POST /v1/admin/playbooks`).

## Per-project choices

Overrides apply system-wide (superadmin) and then per project (project managers); the
project wins. They can switch a playbook off, pin a version, or override parameters. Runs
record the exact version, status, parameters and dataset versions they used.

**Assigning to projects.** The Playbooks page (*Workspace → Playbooks*, open to everyone)
assigns a playbook to projects.

- **Superadmin:** switches a playbook on for every project, or only for the projects
  ticked.
- **Project manager:** decides for the projects they manage.
- **API:** `GET` / `PUT /v1/playbooks/{id}/assignments`. A changed choice keeps that
  project's pinned version and parameters.
- **Project tab:** a project's Playbooks tab lists only what is on for it.

## Translations

English is the base text of a playbook's title and summary.

- **Shipped:** a spec ships other languages under `translations` (for example
  `{"th": {"title": ..., "summary": ...}}`).
- **Saved:** a superadmin saves their own text with
  `PUT /v1/admin/playbooks/{id}/translations/{locale}`. It is stored in
  `playbook_translations` and wins over the shipped text. `DELETE` goes back to the
  shipped one.
- **Display:** the web shows the interface language when a translation exists, otherwise
  English, and labels each card with the language shown.

## Packs

A pack is a separate Python package that imports only `mindgrid.core` and
`mindgrid.functions`, declares its functions and playbooks through entry points, and keeps
its thresholds in parameter models whose defaults are documented. See
[markets-pack.md](markets-pack.md) for a complete example with its parity test.
