"""chunk content hash: an unchanged chunk in a new version reuses its stored vector

Revision: 0017 (after 0016)
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# Mirrors knowledge.library.models.embed_text().
_BACKFILL = """update chunks set content_hash = sha256(convert_to(
  case when heading = '' then text else heading || E'\\n' || text end, 'UTF8'))"""


def upgrade() -> None:
    op.add_column("chunks", sa.Column("content_hash", sa.LargeBinary(), nullable=True))
    op.execute(_BACKFILL)
    op.alter_column("chunks", "content_hash", nullable=False)
    op.create_index("ix_chunks_project_id_content_hash", "chunks", ["project_id", "content_hash"])


def downgrade() -> None:
    op.drop_index("ix_chunks_project_id_content_hash", table_name="chunks")
    op.drop_column("chunks", "content_hash")
