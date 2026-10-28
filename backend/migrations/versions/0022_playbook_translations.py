"""playbook_translations: a playbook's title and summary per language, edited by a
superadmin and readable by everyone signed in

Revision: 0022 (after 0021)
"""

import sqlalchemy as sa
from alembic import op

from mindgrid.db import config as db_config

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_POLICIES = (
    "alter table playbook_translations enable row level security",
    """create policy playbook_translations_read on playbook_translations for select
  using (mindgrid_actor() is not null or mindgrid_is_superadmin())""",
    """create policy playbook_translations_write on playbook_translations for all
  using (mindgrid_is_superadmin()) with check (mindgrid_is_superadmin())""",
)


def upgrade() -> None:
    op.create_table(
        "playbook_translations",
        sa.Column("playbook_id", sa.String(length=100), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column(
            "updated_by", sa.Uuid(), server_default=sa.text("mindgrid_actor()"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("playbook_id", "locale", name=op.f("pk_playbook_translations")),
    )
    for statement in _POLICIES:
        op.execute(statement)
    role = db_config.get_settings().app_role
    op.execute(f"grant select, insert, update, delete on playbook_translations to {role}")


def downgrade() -> None:
    op.drop_table("playbook_translations")
