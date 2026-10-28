"""rate limits: shared sliding-window hits (UNLOGGED: losing them on a crash is harmless)

Revision: 0003 (after 0002)
"""

from alembic import op

from mindgrid.db import config as db_config

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    op.execute("create unlogged table rate_hits (key text not null, at timestamptz not null)")
    op.execute("create index ix_rate_hits_key_at on rate_hits (key, at)")
    op.execute(f"grant select, insert, delete on rate_hits to {app_role}")


def downgrade() -> None:
    op.execute("drop table rate_hits")
