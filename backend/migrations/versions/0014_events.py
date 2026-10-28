"""events: subscriptions, outbox, deliveries, callbacks; RLS; fan-out, claim, result,
replay, ping and purge functions

Revision: 0014 (after 0013)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from mindgrid.db import config as db_config

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


_DEFINER = "security definer set search_path = pg_catalog, public"
_MATCH = """exists (select 1 from unnest(s.event_types) t
                 where t = '*' or t = p_type
                    or (right(t, 2) = '.*' and starts_with(p_type, left(t, length(t) - 1))))"""
_FUNCTIONS = (
    # Record an event and fan it out: matching enabled subscriptions (this project's and
    # system-wide ones) and the one-shot callbacks waiting for this subject and outcome.
    f"""create function mindgrid_emit_event(p_type text, p_project uuid, p_subject text,
                                    p_data jsonb) returns uuid
language plpgsql volatile {_DEFINER} as $$
declare
  ev uuid;
begin
  if mindgrid_actor() is null and not mindgrid_is_superadmin() then
    raise exception 'an account is required' using errcode = '42501';
  end if;
  insert into events (type, project_id, subject, data, created_by)
       values (p_type, p_project, p_subject, p_data, mindgrid_actor()) returning id into ev;
  insert into event_deliveries (event_id, subscription_id, project_id, url, status, attempts,
                                worker, last_error)
  select ev, s.id, p_project, s.url, 'pending', 0, '', '' from event_subscriptions s
   where s.enabled and (s.project_id is null or s.project_id = p_project) and {_MATCH};
  with done as (
    delete from event_callbacks c
     where c.subject = p_subject and p_type = any(c.event_types)
       and c.project_id is not distinct from p_project
    returning c.url, c.created_by)
  insert into event_deliveries (event_id, subscription_id, project_id, url, status, attempts,
                                worker, last_error, requested_by)
  select ev, null, p_project, url, 'pending', 0, '', '', created_by from done;
  return ev;
end
$$""",
    # Due deliveries for one worker: at most one per subscription (a slow receiver only
    # delays itself), expired leases taken over.
    f"""create function mindgrid_claim_deliveries(p_worker text, p_lease interval, p_limit integer)
returns table (delivery_id uuid, attempts integer, url text, subscription_id uuid,
               secret_ciphertext bytea, secret_nonce bytea, secret_version smallint,
               event_id uuid, event_type text, project_id uuid, subject text, data jsonb,
               event_time timestamptz)
language plpgsql volatile {_DEFINER} as $$
#variable_conflict use_column
begin
  return query
  with due as (
    select d.id, row_number() over (partition by coalesce(d.subscription_id, d.id)
                                    order by d.next_attempt_at, d.id) as rn
      from event_deliveries d
     where ((d.status = 'pending' and d.next_attempt_at <= now())
            or (d.status = 'sending' and d.locked_until < now()))
       and (d.subscription_id is null or not exists (
            select 1 from event_deliveries x
             where x.subscription_id = d.subscription_id and x.status = 'sending'
               and x.locked_until >= now()))),
  picked as (
    select d.id from event_deliveries d
     where d.id in (select id from due where rn = 1)
     order by d.next_attempt_at limit p_limit for update skip locked),
  claimed as (
    update event_deliveries d set status = 'sending', attempts = d.attempts + 1,
           worker = p_worker, locked_until = now() + p_lease
      from picked where d.id = picked.id
    returning d.*)
  select c.id, c.attempts, c.url::text, c.subscription_id, s.secret_ciphertext,
         s.secret_nonce, s.secret_version, e.id, e.type::text, e.project_id,
         e.subject::text, e.data, e.created_at
    from claimed c join events e on e.id = c.event_id
    left join event_subscriptions s on s.id = c.subscription_id;
end
$$""",
    f"""create function mindgrid_delivery_result(p_id uuid, p_worker text, p_ok boolean,
            p_code integer, p_error text, p_retry interval, p_gone boolean, p_after integer)
returns delivery_status language plpgsql volatile {_DEFINER} as $$
declare
  st delivery_status;
  sub uuid;
begin
  update event_deliveries set
    status = case when p_ok then 'delivered'::delivery_status
                  when p_retry is null then 'dead'::delivery_status
                  else 'pending'::delivery_status end,
    next_attempt_at = case when p_retry is null then next_attempt_at else now() + p_retry end,
    delivered_at = case when p_ok then now() end,
    last_status_code = p_code, last_error = coalesce(p_error, ''),
    locked_until = null, worker = ''
  where id = p_id and worker = p_worker and status = 'sending'
  returning status, subscription_id into st, sub;
  if sub is not null and st = 'delivered' then
    update event_subscriptions set dead_in_a_row = 0 where id = sub;
  elsif sub is not null and st = 'dead' then
    update event_subscriptions set dead_in_a_row = dead_in_a_row + 1,
           enabled = case when p_gone or dead_in_a_row + 1 >= p_after then false else enabled end,
           disabled_reason = case when p_gone then 'receiver answered 410 Gone'
                                  when dead_in_a_row + 1 >= p_after then 'too many dead deliveries'
                                  else disabled_reason end
     where id = sub;
  end if;
  return st;
end
$$""",
    f"""create function mindgrid_replay_delivery(p_id uuid) returns boolean
language plpgsql volatile {_DEFINER} as $$
begin
  update event_deliveries d set status = 'pending', attempts = 0, next_attempt_at = now(),
         locked_until = null, worker = '', last_error = ''
   where d.id = p_id and d.status in ('dead', 'delivered')
     and (mindgrid_is_superadmin() or d.requested_by = mindgrid_actor()
          or (d.project_id is not null and mindgrid_can_manage_project(d.project_id)));
  return found;
end
$$""",
    f"""create function mindgrid_ping_subscription(p_sub uuid, p_data jsonb) returns uuid
language plpgsql volatile {_DEFINER} as $$
declare
  s event_subscriptions%rowtype;
  ev uuid;
begin
  select * into s from event_subscriptions where id = p_sub;
  if not found or not (mindgrid_is_superadmin() or (s.project_id is not null
                       and mindgrid_can_manage_project(s.project_id))) then
    return null;
  end if;
  insert into events (type, project_id, subject, data, created_by)
       values ('subscription.test', s.project_id, 'subscriptions/' || s.id, p_data,
               mindgrid_actor()) returning id into ev;
  insert into event_deliveries (event_id, subscription_id, project_id, url, status, attempts,
                                worker, last_error)
       values (ev, s.id, s.project_id, s.url, 'pending', 0, '', '');
  return ev;
end
$$""",
    f"""create function mindgrid_purge_events(p_days integer) returns integer
language sql volatile {_DEFINER} as $$
  with gone as (delete from events e
                 where e.created_at < now() - make_interval(days => p_days)
                   and not exists (select 1 from event_deliveries d
                                    where d.event_id = e.id and d.status in ('pending', 'sending'))
                returning 1)
  select count(*)::integer from gone
$$""",
)
_FUNCTION_NAMES = (
    "mindgrid_emit_event(text, uuid, text, jsonb)",
    "mindgrid_claim_deliveries(text, interval, integer)",
    "mindgrid_delivery_result(uuid, text, boolean, integer, text, interval, boolean, integer)",
    "mindgrid_replay_delivery(uuid)",
    "mindgrid_ping_subscription(uuid, jsonb)",
    "mindgrid_purge_events(integer)",
)
_MANAGE = (
    "(project_id is null and mindgrid_is_superadmin())"
    " or (project_id is not null and mindgrid_can_manage_project(project_id))"
)
_POLICIES = (
    "alter table event_subscriptions enable row level security",
    f"create policy event_subscriptions_all on event_subscriptions for all"
    f" using ({_MANAGE}) with check ({_MANAGE})",
    "alter table events enable row level security",
    """create policy events_read on events for select
  using ((project_id is null and mindgrid_is_superadmin())
         or (project_id is not null and mindgrid_can_view_project(project_id)))""",
    "alter table event_deliveries enable row level security",
    f"""create policy event_deliveries_read on event_deliveries for select
  using (requested_by = mindgrid_actor() or {_MANAGE})""",
    "alter table event_callbacks enable row level security",
    """create policy event_callbacks_own on event_callbacks for all
  using (created_by = mindgrid_actor())
  with check (created_by = mindgrid_actor()
              and (project_id is null or mindgrid_can_view_project(project_id)))""",
)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "event_callbacks",
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("event_types", sa.ARRAY(sa.Text()), nullable=False),
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
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_event_callbacks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_callbacks")),
    )
    op.create_index("ix_event_callbacks_subject", "event_callbacks", ["subject"], unique=False)
    op.create_table(
        "event_subscriptions",
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("event_types", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("secret_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("secret_version", sa.SmallInteger(), nullable=False),
        sa.Column("dead_in_a_row", sa.Integer(), nullable=False),
        sa.Column("disabled_reason", sa.String(length=200), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), server_default=sa.text("mindgrid_actor()"), nullable=True
        ),
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
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_event_subscriptions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_subscriptions")),
    )
    op.create_table(
        "events",
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_events_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index(
        "ix_events_project_id_created_at", "events", ["project_id", "created_at"], unique=False
    )
    op.create_table(
        "event_deliveries",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sending", "delivered", "dead", name="delivery_status"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker", sa.String(length=64), nullable=False),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_deliveries_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_event_deliveries_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["event_subscriptions.id"],
            name=op.f("fk_event_deliveries_subscription_id_event_subscriptions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_deliveries")),
    )
    op.create_index(
        "ix_event_deliveries_due",
        "event_deliveries",
        ["next_attempt_at"],
        unique=False,
        postgresql_where=sa.text("status in ('pending', 'sending')"),
    )
    op.create_index("ix_event_deliveries_event_id", "event_deliveries", ["event_id"], unique=False)
    op.create_index(
        "ix_event_deliveries_subscription_id", "event_deliveries", ["subscription_id"], unique=False
    )
    # ### end Alembic commands ###
    app_role = db_config.get_settings().app_role
    for statement in (*_FUNCTIONS, *_POLICIES):
        op.execute(statement)
    for fn in _FUNCTION_NAMES:
        op.execute(f"revoke all on function {fn} from public")
        op.execute(f"grant execute on function {fn} to {app_role}")
    op.execute(f"grant select, insert, update, delete on event_subscriptions to {app_role}")
    op.execute(f"grant select on events, event_deliveries to {app_role}")
    op.execute(f"grant select, insert, delete on event_callbacks to {app_role}")


def downgrade() -> None:
    for fn in _FUNCTION_NAMES:
        op.execute(f"drop function {fn}")
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_event_deliveries_subscription_id", table_name="event_deliveries")
    op.drop_index("ix_event_deliveries_event_id", table_name="event_deliveries")
    op.drop_index(
        "ix_event_deliveries_due",
        table_name="event_deliveries",
        postgresql_where=sa.text("status in ('pending', 'sending')"),
    )
    op.drop_table("event_deliveries")
    op.drop_index("ix_events_project_id_created_at", table_name="events")
    op.drop_table("events")
    op.drop_table("event_subscriptions")
    op.drop_index("ix_event_callbacks_subject", table_name="event_callbacks")
    op.drop_table("event_callbacks")
    # ### end Alembic commands ###
    op.execute("drop type delivery_status")
