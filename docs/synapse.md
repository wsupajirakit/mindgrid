# Synapse: learning from a source repository

Synapse reads a repository's new commits and turns them into a **proposal** that a person
reviews item by item. It never copies a repository wholesale, never trusts a number it
reads, and never edits code by itself.

```
watch → diff → understand → sanitise → dive → propose → review → apply
```

| Step | What happens |
|--|--|
| watch | each source remembers the last commit it learned; a check (on request or every N minutes) compares it with `HEAD` |
| diff | files changed between the two commits (`git diff --name-status`), read-only, inside `MINDGRID_SYNAPSE_ALLOWED_ROOTS` only |
| understand | the source's **mapping** (data) decides: `include` / `exclude` globs (an excluded file is never read), then `rules` (first match wins) — `rules`, `evidence`, `docs` → knowledge; `code` → a code task with the functions its hunks touch; `ignore` |
| sanitise | before anything is stored: e-mail addresses, home folders, the server's own account and machine names, known token and key formats, long secrets, plus the mapping's `redact` patterns; `drop_lines` removes whole lines (e.g. personal holdings). The proposal shows how many redactions were made |
| dive | percentages in added lines ("won 62% of trades") become **measure** items: re-measure on the engine's own data before believing them |
| propose | one proposal per check with changes; event `synapse.proposal_created` (with a link to the review page) |
| review | *Admin → Synapse*: accept or reject each item (superadmin or a manager of the target project) |
| apply | accepted knowledge → a new version of a document in the source's target category (trust tag *claimed*); a removal removes it; accepted code and measure items → `GET /v1/synapse/proposals/{id}/tasks.md`, a checklist for a ticket or pull request |

## Adding a source

1. The operator allows the folder: `MINDGRID_SYNAPSE_ALLOWED_ROOTS=/srv/repos` (absolute
   paths; nothing is allowed by default). In containers, mount the repositories read-only
   into **both** the API (it checks the path when a source is added) and the worker (it
   reads them), e.g. `- /srv/repos:/srv/repos:ro` on both services; the repository may be
   owned by another account (git is told to trust exactly that folder and never run its
   hooks). Inside a container the sanitiser only knows the container's own account and
   host names: add the people's names and host names that may appear in the source to the
   source's `redact` list.
2. A superadmin adds the source (*Admin → Synapse* or `POST /v1/admin/synapse/sources`):
   name, repository folder, target project and category, schedule, and the mapping (start
   from the *Agent skills repository* template and add the repository's private folders to
   `exclude`, private line patterns to `drop_lines`).
3. *Check now*: the first check records the current commit as the starting point (tick
   *propose every file* to import the current state instead). Later checks propose only
   what changed since.
