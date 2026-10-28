"""chunk context: an optional LLM-written line situating the chunk in its document,
searched by meaning and by keyword (contextual retrieval)

Revision: 0018 (after 0017)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def _tsv(expression: str) -> None:
    op.drop_index("ix_chunks_tsv", table_name="chunks", postgresql_using="gin")
    op.drop_column("chunks", "tsv")
    op.add_column(
        "chunks",
        sa.Column("tsv", TSVECTOR(), sa.Computed(expression, persisted=True), nullable=True),
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], unique=False, postgresql_using="gin")


def upgrade() -> None:
    op.add_column("chunks", sa.Column("context", sa.Text(), nullable=False, server_default=""))
    _tsv("to_tsvector('simple', context || ' ' || heading || ' ' || text)")


def downgrade() -> None:
    _tsv("to_tsvector('simple', heading || ' ' || text)")
    op.drop_column("chunks", "context")
