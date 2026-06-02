create table if not exists files (
  id text primary key,

  external_user_id bigint null,
  api_key_id bigint null references api_keys(id) on delete set null,

  filename text not null,
  ext text not null,
  bytes bigint not null default 0 check (bytes >= 0),
  content_type text null,

  storage_backend text not null default 'disk',
  storage_key text not null,
  storage_path text null,

  sha256 text null,

  status text not null default 'uploading',
  error text null,

  created_at timestamptz not null default now(),
  expires_at timestamptz null,
  last_accessed_at timestamptz null,
  deleted_at timestamptz null,

  constraint chk_files_status
    check (status in ('uploading', 'ready', 'failed', 'deleted')),

  constraint chk_files_storage_backend
    check (storage_backend in ('disk', 's3'))
);

create index if not exists idx_files_external_user_id
  on files(external_user_id);

create index if not exists idx_files_api_key_id
  on files(api_key_id);

create index if not exists idx_files_status
  on files(status);

create index if not exists idx_files_created_at
  on files(created_at desc);

create index if not exists idx_files_expires_at
  on files(expires_at);

create index if not exists idx_files_deleted_at
  on files(deleted_at);
