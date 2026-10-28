"""identity: users, sessions, row-level security, sign-in lookup functions

Revision: 0001 (first)
"""

import sqlalchemy as sa
from alembic import op

from mindgrid.db import config as db_config

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_ACTOR_FUNCTIONS = (
    """create function mindgrid_actor() returns uuid language sql stable as
  $$ select nullif(current_setting('mindgrid.user_id', true), '')::uuid $$""",
    """create function mindgrid_is_superadmin() returns boolean language sql stable as
  $$ select coalesce(current_setting('mindgrid.superadmin', true), 'off') = 'on' $$""",
)

_POLICIES = (
    """alter table users enable row level security""",
    """create policy users_read on users for select
  using (id = mindgrid_actor() or mindgrid_is_superadmin())""",
    """create policy users_change on users for update
  using (id = mindgrid_actor() or mindgrid_is_superadmin())
  with check (id = mindgrid_actor() or mindgrid_is_superadmin())""",
    """create policy users_create on users for insert with check (mindgrid_is_superadmin())""",
    """create policy users_remove on users for delete using (mindgrid_is_superadmin())""",
    """alter table sessions enable row level security""",
    """create policy sessions_read on sessions for select
  using (user_id = mindgrid_actor() or mindgrid_is_superadmin())""",
    """create policy sessions_open on sessions for insert
  with check (user_id = mindgrid_actor())""",
    """create policy sessions_change on sessions for update
  using (user_id = mindgrid_actor() or mindgrid_is_superadmin())
  with check (user_id = mindgrid_actor() or mindgrid_is_superadmin())""",
    """create policy sessions_remove on sessions for delete
  using (user_id = mindgrid_actor() or mindgrid_is_superadmin())""",
)

# Sign-in needs the user row before the actor is known: these return only what the
# check needs, for one exact key, and run with the owner's rights.
_LOOKUPS = (
    """create function mindgrid_auth_lookup(p_email text)
returns table (id uuid, password_hash text, status user_status, system_role system_role)
language sql stable security definer set search_path = pg_catalog, public as $$
  select u.id, u.password_hash, u.status, u.system_role
  from users u where lower(u.email) = lower(p_email)
$$""",
    """create function mindgrid_session_lookup(p_token_hash text)
returns table (session_id uuid, user_id uuid, system_role system_role, status user_status,
               expires_at timestamptz, revoked_at timestamptz)
language sql stable security definer set search_path = pg_catalog, public as $$
  select s.id, s.user_id, u.system_role, u.status, s.expires_at, s.revoked_at
  from sessions s join users u on u.id = s.user_id where s.token_hash = p_token_hash
$$""",
    """revoke all on function mindgrid_auth_lookup(text) from public""",
    """revoke all on function mindgrid_session_lookup(text) from public""",
)


def _create_tables() -> None:
    role = sa.Enum("superadmin", "user", name="system_role")
    status = sa.Enum("active", "disabled", name="user_status")
    now = sa.text("now()")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("system_role", role, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column(
            "password_changed_at", sa.DateTime(timezone=True), server_default=now, nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_sessions_user_id_users"
        ),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    _create_tables()
    for statement in (*_ACTOR_FUNCTIONS, *_POLICIES, *_LOOKUPS):
        op.execute(statement)
    op.execute(f"grant select, insert, update, delete on users, sessions to {app_role}")
    op.execute(
        f"grant execute on function mindgrid_auth_lookup(text),"
        f" mindgrid_session_lookup(text) to {app_role}"
    )


def downgrade() -> None:
    op.execute("drop function if exists mindgrid_session_lookup(text)")
    op.execute("drop function if exists mindgrid_auth_lookup(text)")
    op.drop_table("sessions")
    op.drop_table("users")
    op.execute("drop function if exists mindgrid_is_superadmin()")
    op.execute("drop function if exists mindgrid_actor()")
    op.execute("drop type if exists user_status")
    op.execute("drop type if exists system_role")
