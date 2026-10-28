"""tenancy: projects (1 user : many), members, categories, grants, access functions + RLS

Revision: 0002 (after 0001)
"""

import sqlalchemy as sa
from alembic import op

from mindgrid.db import config as db_config

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_DEFINER = "language sql stable security definer set search_path = pg_catalog, public"

# Every access decision lives here; policies and the Python checks call these.
_FUNCTIONS = (
    f"""create function mindgrid_is_project_owner(p uuid) returns boolean {_DEFINER} as $$
  select exists (select 1 from projects where id = p and owner_id = mindgrid_actor())
$$""",
    f"""create function mindgrid_project_role(p uuid) returns project_role {_DEFINER} as $$
  select role from project_members where project_id = p and user_id = mindgrid_actor()
$$""",
    f"""create function mindgrid_can_view_project(p uuid) returns boolean {_DEFINER} as $$
  select mindgrid_is_superadmin() or mindgrid_is_project_owner(p)
      or mindgrid_project_role(p) is not null
$$""",
    f"""create function mindgrid_can_manage_project(p uuid) returns boolean {_DEFINER} as $$
  select mindgrid_is_superadmin() or mindgrid_is_project_owner(p)
      or coalesce((select manage_project from role_levels
                   where role = mindgrid_project_role(p)), false)
$$""",
    f"""create function mindgrid_can_manage_members(p uuid) returns boolean {_DEFINER} as $$
  select mindgrid_is_superadmin() or mindgrid_is_project_owner(p)
      or coalesce((select manage_members from role_levels
                   where role = mindgrid_project_role(p)), false)
$$""",
    f"""create function mindgrid_category_project(c uuid) returns uuid {_DEFINER} as $$
  select project_id from categories where id = c
$$""",
    f"""create function mindgrid_category_level(c uuid) returns smallint {_DEFINER} as $$
  with cat as (select project_id, restricted from categories where id = c),
  granted as (select level from category_grants
              where category_id = c and user_id = mindgrid_actor())
  select (case
    when not exists (select 1 from cat) then 0
    when mindgrid_can_manage_project((select project_id from cat)) then 4
    when mindgrid_project_role((select project_id from cat)) is null then 0
    when (select restricted from cat) then coalesce((select level from granted), 0)
    else greatest(
      (select default_category_level from role_levels
        where role = mindgrid_project_role((select project_id from cat))),
      coalesce((select level from granted), 0))
  end)::smallint
$$""",
)

_POLICIES = (
    "alter table role_levels enable row level security",
    "create policy role_levels_read on role_levels for select using (true)",
    "alter table projects enable row level security",
    # The direct column checks keep INSERT ... RETURNING working: the access functions
    # cannot see a row that the same statement is inserting.
    """create policy projects_read on projects for select
  using (owner_id = mindgrid_actor() or mindgrid_can_view_project(id))""",
    """create policy projects_create on projects for insert
  with check (owner_id = mindgrid_actor() or mindgrid_is_superadmin())""",
    """create policy projects_change on projects for update
  using (mindgrid_can_manage_project(id)) with check (mindgrid_can_manage_project(id))""",
    """create policy projects_remove on projects for delete
  using (owner_id = mindgrid_actor() or mindgrid_is_superadmin())""",
    "alter table project_members enable row level security",
    """create policy members_read on project_members for select
  using (mindgrid_can_view_project(project_id))""",
    """create policy members_write on project_members for all
  using (mindgrid_can_manage_members(project_id))
  with check (mindgrid_can_manage_members(project_id))""",
    "alter table categories enable row level security",
    """create policy categories_read on categories for select
  using (mindgrid_can_manage_project(project_id) or mindgrid_category_level(id) >= 1)""",
    """create policy categories_create on categories for insert
  with check (mindgrid_can_manage_project(project_id))""",
    """create policy categories_change on categories for update
  using (mindgrid_category_level(id) >= 4) with check (mindgrid_category_level(id) >= 4)""",
    """create policy categories_remove on categories for delete
  using (mindgrid_can_manage_project(project_id))""",
    "alter table category_grants enable row level security",
    """create policy grants_read on category_grants for select
  using (user_id = mindgrid_actor()
         or mindgrid_can_manage_members(mindgrid_category_project(category_id)))""",
    """create policy grants_write on category_grants for all
  using (mindgrid_can_manage_members(mindgrid_category_project(category_id)))
  with check (mindgrid_can_manage_members(mindgrid_category_project(category_id)))""",
)

_ROLE_SEED = (
    ("admin", True, True, 4),
    ("editor", False, False, 3),
    ("analyst", False, False, 2),
    ("viewer", False, False, 1),
    ("guest", False, False, 0),
)
_TABLES = "projects, project_members, categories, category_grants"
_FUNCTION_NAMES = (
    "mindgrid_category_level(uuid)",
    "mindgrid_category_project(uuid)",
    "mindgrid_can_manage_members(uuid)",
    "mindgrid_can_manage_project(uuid)",
    "mindgrid_can_view_project(uuid)",
    "mindgrid_project_role(uuid)",
    "mindgrid_is_project_owner(uuid)",
)


def _uuid_pk() -> sa.Column[object]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False)


def _stamps() -> list[sa.Column[object]]:
    now = sa.text("now()")
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    ]


def _create_tables() -> None:
    role = sa.Enum("admin", "editor", "analyst", "viewer", "guest", name="project_role")
    level = sa.SmallInteger()
    op.create_table(
        "role_levels",
        sa.Column("role", role, nullable=False),
        sa.Column("manage_project", sa.Boolean(), nullable=False),
        sa.Column("manage_members", sa.Boolean(), nullable=False),
        sa.Column("default_category_level", level, nullable=False),
        sa.PrimaryKeyConstraint("role", name="pk_role_levels"),
        sa.CheckConstraint("default_category_level between 0 and 4", name="level_range"),
    )
    op.create_table(
        "projects",
        _uuid_pk(),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        *_stamps(),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="RESTRICT", name="fk_projects_owner_id_users"
        ),
        sa.UniqueConstraint("owner_id", "slug", name="uq_projects_owner_slug"),
    )
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.PrimaryKeyConstraint("project_id", "user_id", name="pk_project_members"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_project_members_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_project_members_user_id_users"
        ),
    )
    op.create_table(
        "categories",
        _uuid_pk(),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        *_stamps(),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_categories_project_id_projects",
        ),
        sa.UniqueConstraint("project_id", "slug", name="uq_categories_project_slug"),
    )
    op.create_table(
        "category_grants",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("level", level, nullable=False),
        sa.PrimaryKeyConstraint("category_id", "user_id", name="pk_category_grants"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="CASCADE",
            name="fk_category_grants_category_id_categories",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_category_grants_user_id_users"
        ),
        sa.CheckConstraint("level between 1 and 4", name="level_range"),
    )


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    _create_tables()
    for statement in (*_FUNCTIONS, *_POLICIES):
        op.execute(statement)
    values = ", ".join(  # fixed constants above, not input
        f"('{role}'::project_role, {str(mp).lower()}, {str(mm).lower()}, {lvl})"
        for role, mp, mm, lvl in _ROLE_SEED
    )
    op.execute(f"insert into role_levels values {values}")
    op.execute("comment on table role_levels is 'reference data: seeded by migrations'")
    op.execute(f"grant select, insert, update, delete on {_TABLES} to {app_role}")
    op.execute(f"grant select on role_levels to {app_role}")
    for fn in _FUNCTION_NAMES:
        op.execute(f"revoke all on function {fn} from public")
        op.execute(f"grant execute on function {fn} to {app_role}")


def downgrade() -> None:
    # Tables first: their policies depend on the functions.
    for table in ("category_grants", "categories", "project_members", "projects", "role_levels"):
        op.drop_table(table)
    for fn in _FUNCTION_NAMES:
        op.execute(f"drop function if exists {fn}")
    op.execute("drop type if exists project_role")
