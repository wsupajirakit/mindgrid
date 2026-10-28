"""answers: the text written to a logged question (by the server or reported back by a
client), with its citation check; same readers as the question, purged with it

Revision: 0021 (after 0020)
"""

import sqlalchemy as sa
from alembic import op

from mindgrid.db import config as db_config

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# The asker may attach an answer only to their own question (the subquery runs under the
# recall log's own row-level security).
_POLICIES = (
    "alter table answers enable row level security",
    """create policy answers_read on answers for select
  using (actor_id = mindgrid_actor() or mindgrid_can_manage_project(project_id))""",
    """create policy answers_write on answers for insert
  with check (actor_id = mindgrid_actor() and mindgrid_can_view_project(project_id)
              and exists (select from recall_events r
                          where r.id = recall_event_id and r.actor_id = mindgrid_actor()
                            and r.project_id = answers.project_id))""",
)


def upgrade() -> None:
    op.create_table(
        "answers",
        sa.Column("recall_event_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), server_default=sa.text("mindgrid_actor()"), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("writer", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("check_ok", sa.Boolean(), nullable=True),
        sa.Column("cited", sa.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("unknown", sa.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("uncited", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["recall_event_id"],
            ["recall_events.id"],
            name=op.f("fk_answers_recall_event_id_recall_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_answers_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_answers")),
    )
    op.create_index("ix_answers_recall_event_id", "answers", ["recall_event_id"])
    for statement in _POLICIES:
        op.execute(statement)
    op.execute(f"grant select, insert on answers to {db_config.get_settings().app_role}")


def downgrade() -> None:
    op.drop_index("ix_answers_recall_event_id", table_name="answers")
    op.drop_table("answers")
