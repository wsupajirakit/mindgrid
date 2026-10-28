"""user groups: people in named groups; a project gives a group a role and a category gives
a group a level, so every member (also one added later) inherits them; a person's own
role or grant wins over the group's. Playbooks are off for a project until added: the
pairs a project already ran stay on.

Revision: 0023 (after 0022)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from mindgrid.db import config as db_config

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_DEFINER = "language sql stable security definer set search_path = pg_catalog, public"
_TABLES = "user_groups, user_group_members, project_group_roles, category_group_grants"

# A person's own role wins; otherwise the strongest role among their groups (the enum is
# declared strongest first).
_FUNCTIONS = (
    f"""create or replace function mindgrid_project_role(p uuid) returns project_role
{_DEFINER} as $$
  select case when mindgrid_project_allowed(p) then coalesce(
    (select role from project_members where project_id = p and user_id = mindgrid_actor()),
    (select r.role from project_group_roles r
       join user_group_members m on m.group_id = r.group_id
      where r.project_id = p and m.user_id = mindgrid_actor()
      order by array_position(enum_range(null::project_role), r.role) limit 1))
  end
$$""",
    f"""create or replace function mindgrid_category_level(c uuid) returns smallint
{_DEFINER} as $$
  with cat as (select project_id, restricted from categories where id = c),
  granted as (select coalesce(
    (select level from category_grants where category_id = c and user_id = mindgrid_actor()),
    (select max(g.level) from category_group_grants g
       join user_group_members m on m.group_id = g.group_id
      where g.category_id = c and m.user_id = mindgrid_actor())) as level)
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
    f"""create function mindgrid_project_group_people(p uuid)
returns table (user_id uuid, email text, display_name text, avatar text, group_id uuid,
               group_name text, role project_role)
{_DEFINER} as $$
  select u.id, u.email::text, u.display_name::text, u.avatar::text, g.id, g.name::text,
         r.role
  from project_group_roles r
  join user_groups g on g.id = r.group_id
  join user_group_members m on m.group_id = r.group_id
  join users u on u.id = m.user_id
  where r.project_id = p and mindgrid_can_view_project(p)
  order by u.display_name, g.name
$$""",
)
_ORIGINAL = (
    f"""create or replace function mindgrid_project_role(p uuid) returns project_role
{_DEFINER} as $$
  select role from project_members
  where project_id = p and user_id = mindgrid_actor() and mindgrid_project_allowed(p)
$$""",
    f"""create or replace function mindgrid_category_level(c uuid) returns smallint
{_DEFINER} as $$
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
    "alter table user_groups enable row level security",
    """create policy user_groups_read on user_groups for select
  using (mindgrid_actor() is not null or mindgrid_is_superadmin())""",
    """create policy user_groups_write on user_groups for all
  using (mindgrid_is_superadmin()) with check (mindgrid_is_superadmin())""",
    "alter table user_group_members enable row level security",
    """create policy user_group_members_read on user_group_members for select
  using (mindgrid_is_superadmin() or user_id = mindgrid_actor()
         or exists (select 1 from project_group_roles r
                    where r.group_id = user_group_members.group_id
                    and mindgrid_can_manage_members(r.project_id)))""",
    """create policy user_group_members_write on user_group_members for all
  using (mindgrid_is_superadmin()) with check (mindgrid_is_superadmin())""",
    "alter table project_group_roles enable row level security",
    """create policy project_group_roles_read on project_group_roles for select
  using (mindgrid_can_view_project(project_id))""",
    """create policy project_group_roles_write on project_group_roles for all
  using (mindgrid_can_manage_members(project_id))
  with check (mindgrid_can_manage_members(project_id))""",
    "alter table category_group_grants enable row level security",
    """create policy category_group_grants_read on category_group_grants for select
  using (mindgrid_can_manage_members(mindgrid_category_project(category_id))
         or exists (select 1 from user_group_members m
                    where m.group_id = category_group_grants.group_id
                      and m.user_id = mindgrid_actor()))""",
    """create policy category_group_grants_write on category_group_grants for all
  using (mindgrid_can_manage_members(mindgrid_category_project(category_id)))
  with check (mindgrid_can_manage_members(mindgrid_category_project(category_id)))""",
)
# Playbooks are now off for a project until added: keep on what each project already ran.
_KEEP_USED_PLAYBOOKS = """insert into playbook_overrides (scope, scope_id, playbook_id, enabled,
  params)
select distinct 'project'::setting_scope, r.project_id, r.playbook_id, true, '{}'::jsonb
from runs r
where not exists (select 1 from playbook_overrides o where o.scope = 'project'
                  and o.scope_id = r.project_id and o.playbook_id = r.playbook_id)"""


def _now() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "user_groups",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=2000), server_default="", nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), server_default=sa.text("mindgrid_actor()"), nullable=True
        ),
        _now(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_groups")),
        sa.UniqueConstraint("name", name=op.f("uq_user_groups_name")),
    )
    op.create_table(
        "user_group_members",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _now(),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_groups.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_group_members_group_id_user_groups"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_group_members_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("group_id", "user_id", name=op.f("pk_user_group_members")),
    )
    op.create_index("ix_user_group_members_user_id", "user_group_members", ["user_id"])
    op.create_table(
        "project_group_roles",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(name="project_role", create_type=False),
            nullable=False,
        ),
        _now(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name=op.f("fk_project_group_roles_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_groups.id"],
            ondelete="CASCADE",
            name=op.f("fk_project_group_roles_group_id_user_groups"),
        ),
        sa.PrimaryKeyConstraint("project_id", "group_id", name=op.f("pk_project_group_roles")),
    )
    op.create_table(
        "category_group_grants",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        _now(),
        sa.CheckConstraint("level between 1 and 4", name=op.f("ck_category_group_grants_level")),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="CASCADE",
            name=op.f("fk_category_group_grants_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_groups.id"],
            ondelete="CASCADE",
            name=op.f("fk_category_group_grants_group_id_user_groups"),
        ),
        sa.PrimaryKeyConstraint("category_id", "group_id", name=op.f("pk_category_group_grants")),
    )
    for statement in (*_FUNCTIONS, *_POLICIES):
        op.execute(statement)
    role = db_config.get_settings().app_role
    op.execute(f"grant select, insert, update, delete on {_TABLES} to {role}")
    name = "mindgrid_project_group_people(uuid)"
    op.execute(f"revoke all on function {name} from public")
    op.execute(f"grant execute on function {name} to {role}")
    op.execute(_KEEP_USED_PLAYBOOKS)


def downgrade() -> None:
    op.execute("drop function mindgrid_project_group_people(uuid)")
    for statement in _ORIGINAL:
        op.execute(statement)
    op.execute("drop policy user_group_members_read on user_group_members")
    op.drop_table("category_group_grants")
    op.drop_table("project_group_roles")
    op.drop_index("ix_user_group_members_user_id", table_name="user_group_members")
    op.drop_table("user_group_members")
    op.drop_table("user_groups")
