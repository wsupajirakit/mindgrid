"""settings + secrets: values and sealed secrets per scope, with scope access functions

Revision: 0006 (after 0005)
"""

import sqlalchemy as sa
from alembic import op

from mindgrid.db import config as db_config

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_DEFINER = "language sql stable security definer set search_path = pg_catalog, public"
_FUNCTIONS = (
    f"""create function mindgrid_can_read_scope(s setting_scope, sid uuid) returns boolean
{_DEFINER} as $$
  select case s
    when 'system' then true
    when 'user' then sid = mindgrid_actor() or mindgrid_is_superadmin()
    when 'project' then mindgrid_can_view_project(sid)
    when 'category' then mindgrid_category_level(sid) >= 1
  end
$$""",
    f"""create function mindgrid_can_write_scope(s setting_scope, sid uuid) returns boolean
{_DEFINER} as $$
  select case s
    when 'system' then mindgrid_is_superadmin()
    when 'user' then sid = mindgrid_actor() or mindgrid_is_superadmin()
    when 'project' then mindgrid_can_manage_project(sid)
    when 'category' then mindgrid_category_level(sid) >= 4
  end
$$""",
)
# Settings: read by anyone who may see the scope. Secrets: only those who may change the
# scope even see that a secret exists (its hint and dates).
_POLICIES = (
    "alter table setting_values enable row level security",
    """create policy settings_read on setting_values for select
  using (mindgrid_can_read_scope(scope, scope_id))""",
    """create policy settings_write on setting_values for all
  using (mindgrid_can_write_scope(scope, scope_id))
  with check (mindgrid_can_write_scope(scope, scope_id))""",
    "alter table secret_values enable row level security",
    """create policy secrets_all on secret_values for all
  using (mindgrid_can_write_scope(scope, scope_id))
  with check (mindgrid_can_write_scope(scope, scope_id))""",
)
_FUNCTION_NAMES = (
    "mindgrid_can_read_scope(setting_scope, uuid)",
    "mindgrid_can_write_scope(setting_scope, uuid)",
)


def _common(scope: sa.Enum) -> tuple[list[sa.Column[object]], list[sa.Column[object]]]:
    """Columns before and after the table-specific ones."""
    now = sa.text("now()")
    head = [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("scope", scope, nullable=False),
        sa.Column("scope_id", sa.Uuid()),
    ]
    tail = [
        sa.Column("updated_by", sa.Uuid(), server_default=sa.text("mindgrid_actor()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    ]
    return head, tail


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    scope = sa.Enum("system", "user", "project", "category", name="setting_scope")
    rule = "(scope = 'system') = (scope_id is null)"
    head, tail = _common(scope)
    op.create_table(
        "setting_values",
        *head,
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.dialects.postgresql.JSONB(), nullable=False),
        *tail,
        sa.PrimaryKeyConstraint("id", name="pk_setting_values"),
        sa.CheckConstraint(rule, name="scope_id_rule"),
        sa.UniqueConstraint(
            "scope",
            "scope_id",
            "key",
            name="uq_setting_values_scope_key",
            postgresql_nulls_not_distinct=True,
        ),
    )
    head, tail = _common(sa.Enum(name="setting_scope", create_type=False))
    op.create_table(
        "secret_values",
        *head,
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column("hint", sa.String(8), nullable=False),
        *tail,
        sa.PrimaryKeyConstraint("id", name="pk_secret_values"),
        sa.CheckConstraint(rule, name="scope_id_rule"),
        sa.UniqueConstraint(
            "scope",
            "scope_id",
            "name",
            name="uq_secret_values_scope_name",
            postgresql_nulls_not_distinct=True,
        ),
    )
    for statement in (*_FUNCTIONS, *_POLICIES):
        op.execute(statement)
    op.execute(
        f"grant select, insert, update, delete on setting_values, secret_values to {app_role}"
    )
    for fn in _FUNCTION_NAMES:
        op.execute(f"revoke all on function {fn} from public")
        op.execute(f"grant execute on function {fn} to {app_role}")


def downgrade() -> None:
    op.drop_table("secret_values")
    op.drop_table("setting_values")
    for fn in _FUNCTION_NAMES:
        op.execute(f"drop function if exists {fn}")
    op.execute("drop type if exists setting_scope")
