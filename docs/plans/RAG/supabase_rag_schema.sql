-- Supabase schema for BotSalinha RAG dual-write backend.
-- Run this in Supabase SQL editor before enabling BOTSALINHA_RAG__SUPABASE__ENABLED=true.

create extension if not exists vector with schema extensions;

create table if not exists rag_documents (
  id bigserial primary key,
  nome text not null,
  arquivo_origem text not null,
  content_hash text unique,
  schema_version integer not null default 1,
  chunk_count integer not null default 0,
  token_count integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists rag_chunks (
  id text primary key,
  documento_id bigint not null references rag_documents(id) on delete cascade,
  texto text not null,
  metadados jsonb not null default '{}'::jsonb,
  content_hash text,
  metadata_version integer not null default 1,
  token_count integer not null default 0,
  embedding extensions.vector(1536),
  created_at timestamptz not null default now()
);

create index if not exists ix_rag_chunks_documento_id on rag_chunks(documento_id);
create index if not exists ix_rag_chunks_content_hash on rag_chunks(content_hash);
create index if not exists ix_rag_chunks_metadados_gin on rag_chunks using gin (metadados);
create index if not exists ix_rag_chunks_embedding_ivfflat
  on rag_chunks using ivfflat (embedding extensions.vector_cosine_ops)
  with (lists = 100);

create table if not exists content_links (
  id uuid primary key default gen_random_uuid(),
  article_chunk_id text not null references rag_chunks(id) on delete cascade,
  linked_chunk_id text not null references rag_chunks(id) on delete cascade,
  link_type text not null check (link_type in ('interprets', 'charged_in', 'updates')),
  created_at timestamptz not null default now(),
  unique (article_chunk_id, linked_chunk_id, link_type)
);

create index if not exists ix_content_links_article_link_type
  on content_links(article_chunk_id, link_type);
create index if not exists ix_content_links_linked_chunk
  on content_links(linked_chunk_id);

-- Security hardening (RLS): keep tables inaccessible to anon/authenticated by default.
alter table if exists rag_documents enable row level security;
alter table if exists rag_chunks enable row level security;
alter table if exists content_links enable row level security;

-- Service-role-only access policies (used by backend ingestion/query jobs).
drop policy if exists rag_documents_service_role_all on rag_documents;
create policy rag_documents_service_role_all
  on rag_documents
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists rag_chunks_service_role_all on rag_chunks;
create policy rag_chunks_service_role_all
  on rag_chunks
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists content_links_service_role_all on content_links;
create policy content_links_service_role_all
  on content_links
  for all
  to service_role
  using (true)
  with check (true);

create or replace function match_rag_chunks(
  query_embedding extensions.vector(1536),
  match_count int default 5,
  min_similarity float default 0.4,
  metadata_filter jsonb default '{}'::jsonb,
  documento_id_filter bigint default null
)
returns table (
  id text,
  documento_id bigint,
  texto text,
  metadados jsonb,
  token_count int,
  posicao_documento float,
  similarity float
)
language plpgsql
set search_path = public
as $$
begin
  return query
  select
    c.id,
    c.documento_id,
    c.texto,
    c.metadados,
    c.token_count,
    coalesce((c.metadados->>'posicao_documento')::float, 0.0) as posicao_documento,
    1 - (c.embedding <=> query_embedding) as similarity
  from rag_chunks c
  where c.embedding is not null
    and (documento_id_filter is null or c.documento_id = documento_id_filter)
    and (metadata_filter = '{}'::jsonb or c.metadados @> metadata_filter)
    and (1 - (c.embedding <=> query_embedding)) >= min_similarity
  order by c.embedding <=> query_embedding
  limit match_count;
end;
$$;
