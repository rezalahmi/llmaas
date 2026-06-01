create table if not exists api_keys (
  id bigserial primary key,

  external_user_id bigint,
  user_name text not null,

  key_prefix text not null,
  key_hash text not null unique,

  quota bigint not null default 0,
  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  last_used_at timestamptz
);

create index if not exists idx_api_keys_external_user_id on api_keys(external_user_id);
create index if not exists idx_api_keys_is_active on api_keys(is_active);
