"""dataset_versions.records_path: where the records sit inside a JSON file, kept with the
version so reading it later finds them (versions synced before get it from their
connector's resource)

Revision: 0024 (after 0023)
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

_BACKFILL = """update dataset_versions v set records_path = r.value->>'records_path'
from datasets d, connectors c, jsonb_array_elements(c.spec->'resources') r(value)
where d.id = v.dataset_id and c.project_id = d.project_id
  and r.value->>'dataset' = d.name and coalesce(r.value->>'records_path', '') <> ''
  and v.media_type = 'application/json'"""


def upgrade() -> None:
    op.add_column(
        "dataset_versions",
        sa.Column("records_path", sa.String(length=200), server_default="", nullable=False),
    )
    op.execute(_BACKFILL)


def downgrade() -> None:
    op.drop_column("dataset_versions", "records_path")
