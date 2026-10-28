# Who can do what

Every rule below is enforced in the database (row-level security calls the same SQL
functions the API uses), so the API and the data can never disagree.

## Projects

- **Owner:** the person who created the project; can do everything in it.
- **Role:** one of `admin`, `editor`, `analyst`, `viewer`, `guest` (strongest first). What
  each role may do is reference data in `role_levels`.
- **Own role:** set for one person (*Project → Members → People*).
- **Group role:** a user group can have a role in a project (*Members → Groups*). Every member
  of the group gets that role, including people who join the group later. Removing the
  group, or removing someone from it, ends what it gave at once.
- **Precedence:** a person's own role wins over their groups' roles. Without an own role,
  the strongest role among their groups applies.

## Categories

Knowledge lives in categories inside a project.

- **Open category:** every member gets their role's default level. A grant can raise it.
- **Restricted category:** only the owner, project managers, and people or groups with a
  grant on it can see it.
- **Grants:** a level (`read`, `run`, `edit`, `manage`), given to a person or to a group
  (*Categories → Access*). A person's own grant wins over their groups' grants; otherwise
  the strongest group grant applies.
- **API:**
  - `GET /v1/categories/{id}/access` lists each person's level and where it comes from.
  - `PUT /v1/categories/{id}/grants/{user_id}` sets a person's grant.
  - `PUT /v1/categories/{id}/group-grants/{group_id}` sets a group's grant. Level `0`
    removes a grant.

## Groups

A superadmin manages groups (*Administration → Groups*, `/v1/admin/groups`):

- create a group, rename it, or delete it;
- add or remove its members;
- choose a person's groups when creating them, or later in *Users → Groups*.

Anyone signed in can list groups (`GET /v1/groups`) to give one a role or a grant.

## What each project has

Each project builds its own knowledge (categories and documents) and its own set of
playbooks.

- **Playbooks:** a playbook is off in a project until it is added there (*Project →
  Playbooks → Add playbook*, or assigned on the Playbooks page). A superadmin can switch one
  on for every project. When migration 0023 introduced this rule, every playbook a project
  had already run stayed on.
- **Copying (superadmin):** *Copy to project* on a project's page
  (`POST /v1/admin/projects/{id}/copy`). It copies the chosen categories into another
  project, with each document's current version, chunks and vectors (nothing is embedded
  again), and optionally the playbook choices.
  - Grants are not copied, because the other project has its own people.
  - A short name already used in the target project gets a number added.
