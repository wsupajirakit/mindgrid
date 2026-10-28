"""eval judgements: an LLM's grading of an eval run (append-only, same access as runs)

Revision: 0019 (after 0018)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from mindgrid.db import config as db_config

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_POLICIES = (
    "alter table eval_judgements enable row level security",
    """create policy eval_judgements_read on eval_judgements for select
  using (mindgrid_can_view_project(project_id))""",
    """create policy eval_judgements_write on eval_judgements for insert
  with check (mindgrid_can_view_project(project_id)
              and (created_by = mindgrid_actor()
                   or (created_by is null and mindgrid_actor() is null
                       and mindgrid_is_superadmin())))""",
)


def upgrade() -> None:
    op.create_table(
        "eval_judgements",
        sa.Column("eval_run_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("judge", sa.String(length=200), nullable=False),
        sa.Column("answerer", sa.String(length=200), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), server_default=sa.text("mindgrid_actor()"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["eval_run_id"],
            ["eval_runs.id"],
            name=op.f("fk_eval_judgements_eval_run_id_eval_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_eval_judgements_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_judgements")),
    )
    op.create_index("ix_eval_judgements_eval_run_id", "eval_judgements", ["eval_run_id"])
    for statement in _POLICIES:
        op.execute(statement)
    op.execute(f"grant select, insert on eval_judgements to {db_config.get_settings().app_role}")


def downgrade() -> None:
    op.drop_index("ix_eval_judgements_eval_run_id", table_name="eval_judgements")
    op.drop_table("eval_judgements")
