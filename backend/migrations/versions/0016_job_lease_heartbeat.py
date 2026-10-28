"""job lease heartbeat: the worker running a job extends its lease while it works

Revision: 0016 (after 0015)
"""

from alembic import op

from mindgrid.db import config as db_config

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


_EXTEND = """create function mindgrid_extend_job_lease(p_id uuid, p_worker text, p_lease interval)
returns boolean language sql volatile security definer set search_path = pg_catalog, public as $$
  update jobs set locked_until = now() + p_lease, updated_at = now()
   where id = p_id and worker = p_worker and status = 'running'
  returning true
$$"""
_NAME = "mindgrid_extend_job_lease(uuid, text, interval)"


def upgrade() -> None:
    app_role = db_config.get_settings().app_role
    op.execute(_EXTEND)
    op.execute(f"revoke all on function {_NAME} from public")
    op.execute(f"grant execute on function {_NAME} to {app_role}")


def downgrade() -> None:
    op.execute(f"drop function {_NAME}")
