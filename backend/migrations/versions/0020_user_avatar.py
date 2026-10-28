"""user avatar: a picture chosen from the web app's built-in set ("" = initials); member
profiles carry it so project members see each other's picture

Revision: 0020 (after 0019)
"""

import sqlalchemy as sa
from alembic import op

from mindgrid.db import config as db_config

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_NAME = "mindgrid_project_member_profiles(uuid)"
_BODY = """language sql stable security definer set search_path = pg_catalog, public as $$
  select u.id, u.email::text, u.display_name::text, m.role{extra}
  from project_members m join users u on u.id = m.user_id
  where m.project_id = p and mindgrid_can_view_project(p)
  order by u.display_name
$$"""
_WITH_AVATAR = (
    "create function mindgrid_project_member_profiles(p uuid)\n"
    "returns table (user_id uuid, email text, display_name text, role project_role,"
    " avatar text)\n" + _BODY.format(extra=", u.avatar::text")
)
_WITHOUT_AVATAR = (
    "create function mindgrid_project_member_profiles(p uuid)\n"
    "returns table (user_id uuid, email text, display_name text, role project_role)\n"
    + _BODY.format(extra="")
)


def _replace(definition: str) -> None:
    app_role = db_config.get_settings().app_role
    op.execute(f"drop function if exists {_NAME}")
    op.execute(definition)
    op.execute(f"revoke all on function {_NAME} from public")
    op.execute(f"grant execute on function {_NAME} to {app_role}")


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("avatar", sa.String(length=40), nullable=False, server_default="")
    )
    _replace(_WITH_AVATAR)


def downgrade() -> None:
    _replace(_WITHOUT_AVATAR)
    op.drop_column("users", "avatar")
