"""jobs queue (claim / finish functions), embedding spaces, chunk embeddings; RLS

Revision: 0010 (after 0009)
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from mindgrid.db import config as db_config

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


_DEFINER = "security definer set search_path = pg_catalog, public"
_FUNCTIONS = (
    # One ready job for this worker, leased; leases that ran out on the last try fail.
    # The queuing account is returned only while it is active, with its current role.
    f"""create function mindgrid_claim_job(p_worker text, p_lease interval, p_kinds text[])
returns table (id uuid, kind text, payload jsonb, attempts integer, created_by uuid,
               actor_projects uuid[], actor_superadmin boolean)
language plpgsql volatile {_DEFINER} as $$
#variable_conflict use_column
declare
  j jobs%rowtype;
begin
  update jobs set status = 'failed', locked_until = null, worker = '', finished_at = now(),
         updated_at = now(),
         last_error = case when last_error = '' then 'lease expired' else last_error end
   where status = 'running' and locked_until < now() and attempts >= max_attempts;
  select * into j from jobs
   where kind = any(p_kinds) and attempts < max_attempts
     and ((status = 'queued' and run_after <= now())
          or (status = 'running' and locked_until < now()))
   order by run_after, id limit 1 for update skip locked;
  if not found then
    return;
  end if;
  update jobs set status = 'running', attempts = attempts + 1, worker = p_worker,
         locked_until = now() + p_lease, updated_at = now()
   where jobs.id = j.id;
  return query
    select j.id, j.kind::text, j.payload, j.attempts + 1,
           case when u.status = 'active' then j.created_by end, j.actor_projects,
           coalesce(u.status = 'active' and u.system_role = 'superadmin', false)
      from (select 1) as one left join users u on u.id = j.created_by;
end
$$""",
    # Done, or the error recorded and the next try queued (failed when final or the last).
    # Only the worker holding the lease may finish a job; otherwise the result is null.
    f"""create function mindgrid_finish_job(p_id uuid, p_worker text, p_error text,
                                    p_final boolean, p_retry interval)
returns job_status language sql volatile {_DEFINER} as $$
  update jobs set
    status = case when p_error is null then 'done'::job_status
                  when p_final or attempts >= max_attempts then 'failed'::job_status
                  else 'queued'::job_status end,
    run_after = case when p_error is null then run_after else now() + p_retry end,
    finished_at = case when p_error is null or p_final or attempts >= max_attempts
                       then now() end,
    last_error = coalesce(p_error, ''), locked_until = null, worker = '', updated_at = now()
  where id = p_id and worker = p_worker and status = 'running'
  returning status
$$""",
    # Register a space and build its partial HNSW index (vectors cast to the space's size).
    f"""create function mindgrid_ensure_embedding_space(p_key text, p_provider text,
                                                p_model text, p_dims integer)
returns void language plpgsql volatile {_DEFINER} as $$
declare
  idx text := 'ix_chunk_embeddings_hnsw_' || left(md5(p_key), 16);
begin
  if mindgrid_actor() is null then
    raise exception 'an account is required' using errcode = '42501';
  end if;
  if p_dims < 1 or p_dims > 2000 then
    raise exception 'vector size % cannot be indexed', p_dims;
  end if;
  insert into embedding_spaces (key, provider, model, dims)
       values (p_key, p_provider, p_model, p_dims) on conflict (key) do nothing;
  if exists (select 1 from embedding_spaces where key = p_key and dims <> p_dims) then
    raise exception 'embedding space % has another vector size', p_key;
  end if;
  if to_regclass(idx) is null then
    execute format('create index %I on chunk_embeddings using hnsw'
                   ' ((embedding::vector(%s)) vector_cosine_ops) where space = %L',
                   idx, p_dims, p_key);
  end if;
end
$$""",
    # A model-provider key for work in a project: the project's own, else the system one.
    f"""create function mindgrid_provider_secret(p_project uuid, p_name text)
returns table (ciphertext bytea, nonce bytea, key_version smallint, scope text,
               scope_id uuid)
language sql stable {_DEFINER} as $$
  select s.ciphertext, s.nonce, s.key_version, s.scope::text, s.scope_id
    from secret_values s
   where p_name like 'provider.%' and s.name = p_name and mindgrid_can_view_project(p_project)
     and ((s.scope = 'project' and s.scope_id = p_project)
          or (s.scope = 'system' and s.scope_id is null))
   order by (s.scope = 'project') desc limit 1
$$""",
)
_FUNCTION_NAMES = (
    "mindgrid_claim_job(text, interval, text[])",
    "mindgrid_finish_job(uuid, text, text, boolean, interval)",
    "mindgrid_ensure_embedding_space(text, text, text, integer)",
    "mindgrid_provider_secret(uuid, text)",
)
_READ = "category_id = any((select mindgrid_readable_categories())::uuid[])"
_EDIT = "category_id = any((select mindgrid_editable_categories())::uuid[])"
_POLICIES = (
    "alter table jobs enable row level security",
    """create policy jobs_read on jobs for select
  using (created_by = mindgrid_actor() or mindgrid_is_superadmin()
         or (project_id is not null and mindgrid_can_view_project(project_id)))""",
    """create policy jobs_queue on jobs for insert
  with check (created_by = mindgrid_actor() and status = 'queued' and attempts = 0
              and (project_id is null or mindgrid_can_view_project(project_id)))""",
    "alter table chunk_embeddings enable row level security",
    f"create policy chunk_embeddings_read on chunk_embeddings for select using ({_READ})",
    f"create policy chunk_embeddings_write on chunk_embeddings for insert with check ({_EDIT})",
    f"create policy chunk_embeddings_remove on chunk_embeddings for delete using ({_EDIT})",
)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "embedding_spaces",
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("dims", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_embedding_spaces")),
    )
    op.create_table(
        "jobs",
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "done", "failed", name="job_status"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), server_default=sa.text("mindgrid_actor()"), nullable=True
        ),
        sa.Column(
            "actor_projects",
            sa.ARRAY(sa.Uuid()),
            server_default=sa.text(
                "coalesce(string_to_array(nullif(current_setting('mindgrid.projects', true),"
                " ''), ',')::uuid[], '{}')"
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "run_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker", sa.String(length=64), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_jobs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"], unique=False)
    op.create_index(
        "ix_jobs_ready",
        "jobs",
        ["run_after"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("space", sa.String(length=300), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_chunk_embeddings_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            name=op.f("fk_chunk_embeddings_chunk_id_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_chunk_embeddings_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space"],
            ["embedding_spaces.key"],
            name=op.f("fk_chunk_embeddings_space_embedding_spaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id", "space", name=op.f("pk_chunk_embeddings")),
    )
    op.create_index(
        "ix_chunk_embeddings_category_id", "chunk_embeddings", ["category_id"], unique=False
    )
    # ### end Alembic commands ###
    app_role = db_config.get_settings().app_role
    for statement in _FUNCTIONS + _POLICIES:
        op.execute(statement)
    for fn in _FUNCTION_NAMES:
        op.execute(f"revoke all on function {fn} from public")
        op.execute(f"grant execute on function {fn} to {app_role}")
    op.execute(f"grant select, insert on jobs to {app_role}")
    op.execute(f"grant select on embedding_spaces to {app_role}")
    op.execute(f"grant select, insert, delete on chunk_embeddings to {app_role}")


def downgrade() -> None:
    for fn in _FUNCTION_NAMES:
        op.execute(f"drop function {fn}")
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_chunk_embeddings_category_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_index("ix_jobs_ready", table_name="jobs", postgresql_where=sa.text("status = 'queued'"))
    op.drop_index("ix_jobs_project_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("embedding_spaces")
    # ### end Alembic commands ###
    op.execute("drop type job_status")
