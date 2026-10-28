"""member profiles: email + display name of a project's members, for those who see it

Revision: 0007 (after 0006)
"""

from alembic import op

from mindgrid.db import config as db_config

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Users' rows are private (row-level security); members of a project see each other's
# name and email only, and only through this function.
_FUNCTION = """create function mindgrid_project_member_profiles(p uuid)
returns table (user_id uuid, email text, display_name text, role project_role)
language sql stable security definer set search_path = pg_catalog, public as $$
  select u.id, u.email::text, u.display_name::text, m.role
  from project_members m join users u on u.id = m.user_id
  where m.project_id = p and mindgrid_can_view_project(p)
  order by u.display_name
$$"""
_NAME = "mindgrid_project_member_profiles(uuid)"


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    op.execute(_FUNCTION)
    op.execute(f"revoke all on function {_NAME} from public")
    op.execute(f"grant execute on function {_NAME} to {app_role}")


def downgrade() -> None:
    op.execute(f"drop function if exists {_NAME}")
