-- TaskFlow cloud sync schema. Run once in the Supabase SQL editor; running it again is safe.
-- Clients read and write only through the functions below. Every row belongs to auth.uid().

create table if not exists public.taskflow_cursors (
  user_id uuid primary key references auth.users (id) on delete cascade,
  seq bigint not null default 0
);

create table if not exists public.taskflow_records (
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('project', 'task')),
  id text not null check (length(id) between 1 and 100),
  revision bigint not null,
  deleted boolean not null default false,
  data jsonb,
  seq bigint not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, kind, id),
  check (deleted or data is not null)
);
create index if not exists taskflow_records_seq on public.taskflow_records (user_id, seq);

create table if not exists public.taskflow_events (
  user_id uuid not null references auth.users (id) on delete cascade,
  id text not null check (length(id) between 1 and 100),
  project_id text,
  task_id text not null,
  payload jsonb not null,
  seq bigint not null,
  primary key (user_id, id)
);
create index if not exists taskflow_events_seq on public.taskflow_events (user_id, seq);

alter table public.taskflow_cursors enable row level security;
alter table public.taskflow_records enable row level security;
alter table public.taskflow_events enable row level security;

drop policy if exists "taskflow own cursor" on public.taskflow_cursors;
create policy "taskflow own cursor" on public.taskflow_cursors
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "taskflow own records" on public.taskflow_records;
create policy "taskflow own records" on public.taskflow_records
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "taskflow own events" on public.taskflow_events;
create policy "taskflow own events" on public.taskflow_events
  for select to authenticated using ((select auth.uid()) = user_id);

-- No direct writes: revision checks live in the functions.
revoke insert, update, delete, truncate on public.taskflow_cursors, public.taskflow_records, public.taskflow_events
  from anon, authenticated;
revoke all on public.taskflow_cursors, public.taskflow_records, public.taskflow_events from anon;

-- Holding the caller's cursor row until commit makes sequence order equal commit order per user,
-- so a pull can never skip a change that commits late.
create or replace function public.taskflow_next_seq(p_user uuid)
returns bigint
language sql
security definer
set search_path = ''
as $$
  insert into public.taskflow_cursors as c (user_id, seq) values (p_user, 1)
  on conflict (user_id) do update set seq = c.seq + 1
  returning seq;
$$;
revoke all on function public.taskflow_next_seq(uuid) from public, anon, authenticated;

create or replace function public.taskflow_push_many(p_items jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_item jsonb;
  v_record jsonb;
  v_current public.taskflow_records;
  v_base bigint;
  v_results jsonb := '[]'::jsonb;
begin
  if v_user is null then
    raise exception 'TaskFlow sync requires a signed-in user' using errcode = '42501';
  end if;
  if jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) > 200 then
    raise exception 'Push at most 200 records at once' using errcode = '22023';
  end if;
  -- Lock the cursor first so concurrent pushes from one user serialize.
  perform 1 from public.taskflow_cursors where user_id = v_user for update;
  for v_item in select value from jsonb_array_elements(p_items) loop
    v_record := v_item -> 'record';
    v_base := (v_item ->> 'base_revision')::bigint;
    select * into v_current from public.taskflow_records
      where user_id = v_user and kind = v_record ->> 'kind' and id = v_record ->> 'id'
      for update;
    if (case when found then v_current.revision else null end) is distinct from v_base then
      v_results := v_results || jsonb_build_array(jsonb_build_object(
        'accepted', false,
        'record', case when found then jsonb_build_object(
          'kind', v_current.kind, 'id', v_current.id, 'revision', v_current.revision,
          'deleted', v_current.deleted, 'data', v_current.data) else null end));
      continue;
    end if;
    insert into public.taskflow_records as r (user_id, kind, id, revision, deleted, data, seq, updated_at)
    values (v_user, v_record ->> 'kind', v_record ->> 'id', (v_record ->> 'revision')::bigint,
            coalesce((v_record ->> 'deleted')::boolean, false),
            case when coalesce((v_record ->> 'deleted')::boolean, false) then null else v_record -> 'data' end,
            public.taskflow_next_seq(v_user), now())
    on conflict (user_id, kind, id) do update
      set revision = excluded.revision, deleted = excluded.deleted, data = excluded.data,
          seq = excluded.seq, updated_at = excluded.updated_at;
    v_results := v_results || jsonb_build_array(jsonb_build_object('accepted', true, 'record', v_record));
  end loop;
  return v_results;
end;
$$;

create or replace function public.taskflow_push_events(p_events jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_event jsonb;
begin
  if v_user is null then
    raise exception 'TaskFlow sync requires a signed-in user' using errcode = '42501';
  end if;
  if jsonb_typeof(p_events) <> 'array' or jsonb_array_length(p_events) > 500 then
    raise exception 'Push at most 500 events at once' using errcode = '22023';
  end if;
  perform 1 from public.taskflow_cursors where user_id = v_user for update;
  for v_event in select value from jsonb_array_elements(p_events) loop
    if not exists (select 1 from public.taskflow_events where user_id = v_user and id = v_event ->> 'id') then
      insert into public.taskflow_events (user_id, id, project_id, task_id, payload, seq)
      values (v_user, v_event ->> 'id', v_event ->> 'project_id', v_event ->> 'task_id', v_event -> 'payload',
              public.taskflow_next_seq(v_user));
    end if;
  end loop;
end;
$$;

create or replace function public.taskflow_pull(p_cursor bigint, p_limit integer default 500)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_latest bigint;
  v_upto bigint;
begin
  if v_user is null then
    raise exception 'TaskFlow sync requires a signed-in user' using errcode = '42501';
  end if;
  select coalesce((select seq from public.taskflow_cursors where user_id = v_user), 0) into v_latest;
  select seq into v_upto from (
    select seq from public.taskflow_records where user_id = v_user and seq > p_cursor
    union all
    select seq from public.taskflow_events where user_id = v_user and seq > p_cursor
    order by seq offset greatest(least(p_limit, 1000), 1) - 1 limit 1) page;
  v_upto := coalesce(v_upto, v_latest);
  return jsonb_build_object(
    'records', coalesce((select jsonb_agg(jsonb_build_object(
        'kind', kind, 'id', id, 'revision', revision, 'deleted', deleted, 'data', data) order by seq)
      from public.taskflow_records where user_id = v_user and seq > p_cursor and seq <= v_upto), '[]'::jsonb),
    'events', coalesce((select jsonb_agg(jsonb_build_object(
        'id', id, 'project_id', project_id, 'task_id', task_id, 'payload', payload) order by seq)
      from public.taskflow_events where user_id = v_user and seq > p_cursor and seq <= v_upto), '[]'::jsonb),
    'cursor', v_upto,
    'more', v_upto < v_latest);
end;
$$;

revoke all on function public.taskflow_push_many(jsonb), public.taskflow_push_events(jsonb),
  public.taskflow_pull(bigint, integer) from public, anon;
grant execute on function public.taskflow_push_many(jsonb), public.taskflow_push_events(jsonb),
  public.taskflow_pull(bigint, integer) to authenticated;
