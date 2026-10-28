"""member lookup: resolve an email to a user id for project invitations

Revision: 0004 (after 0003)
"""

from alembic import op

from mindgrid.db import config as db_config

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# Only the id, only for an exact email; the API calls it after checking that the caller
# manages the project's members.
_FUNCTION = """create function mindgrid_user_id_for_email(p_email text) returns uuid
language sql stable security definer set search_path = pg_catalog, public as $$
  select id from users where lower(email) = lower(p_email) and status = 'active'
$$"""


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    op.execute(_FUNCTION)
    op.execute("revoke all on function mindgrid_user_id_for_email(text) from public")
    op.execute(f"grant execute on function mindgrid_user_id_for_email(text) to {app_role}")


def downgrade() -> None:
    op.execute("drop function if exists mindgrid_user_id_for_email(text)")
