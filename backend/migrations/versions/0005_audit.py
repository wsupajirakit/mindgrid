"""audit: append-only events with row-level security

Revision: 0005 (after 0004)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from mindgrid.db import config as db_config

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_POLICIES = (
    "alter table audit_events enable row level security",
    # Readable by a superadmin, by whoever may manage the project, and by the actor itself.
    """create policy audit_read on audit_events for select
  using (mindgrid_is_superadmin() or actor_user_id = mindgrid_actor()
         or (project_id is not null and mindgrid_can_manage_project(project_id)))""",
    # The recorded actor must be the acting principal: no forged entries.
    """create policy audit_write on audit_events for insert
  with check (actor_user_id is not distinct from mindgrid_actor()
              and actor_superadmin = mindgrid_is_superadmin())""",
)


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    now = sa.text("now()")
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), server_default=sa.text("mindgrid_actor()")),
        sa.Column(
            "actor_superadmin",
            sa.Boolean(),
            server_default=sa.text("mindgrid_is_superadmin()"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_audit_events_actor_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="SET NULL",
            name="fk_audit_events_project_id_projects",
        ),
    )
    op.create_index("ix_audit_events_project_id_id", "audit_events", ["project_id", "id"])
    op.create_index("ix_audit_events_actor_user_id_id", "audit_events", ["actor_user_id", "id"])
    for statement in _POLICIES:
        op.execute(statement)
    op.execute(f"grant select, insert on audit_events to {app_role}")  # never update/delete


def downgrade() -> None:
    op.drop_table("audit_events")
