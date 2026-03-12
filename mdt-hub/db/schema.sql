create table if not exists cases (
  case_id text primary key,
  status text not null,
  opened_at timestamptz not null default now(),
  closed_at timestamptz,
  patient_summary jsonb not null,
  danger_flag boolean not null default false,
  final_conclusion jsonb
);

create table if not exists mdt_events (
  event_id bigserial primary key,
  case_id text not null references cases(case_id) on delete cascade,
  round_no int not null,
  event_type text not null,
  speaker text not null,
  specialty text,
  payload jsonb not null,
  confidence numeric,
  reply_to_event_id bigint,
  created_at timestamptz not null default now()
);

create index if not exists idx_mdt_events_case_time on mdt_events(case_id, created_at);
create index if not exists idx_mdt_events_type on mdt_events(event_type);

create table if not exists mdt_issues (
  issue_id bigserial primary key,
  case_id text not null references cases(case_id) on delete cascade,
  topic text not null,
  status text not null,
  supporting_agents text[] default '{}',
  opposing_agents text[] default '{}',
  resolution text,
  updated_at timestamptz not null default now()
);
