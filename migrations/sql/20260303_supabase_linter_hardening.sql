-- Fix Supabase linter warnings:
-- 1) function_search_path_mutable on public.match_rag_chunks
-- 2) extension_in_public for vector extension

begin;

create schema if not exists extensions;

-- Move pgvector extension out of public schema if needed.
-- Safe to run repeatedly.
alter extension vector set schema extensions;

create or replace function public.match_rag_chunks(
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
  from public.rag_chunks c
  where c.embedding is not null
    and (documento_id_filter is null or c.documento_id = documento_id_filter)
    and (metadata_filter = '{}'::jsonb or c.metadados @> metadata_filter)
    and (1 - (c.embedding <=> query_embedding)) >= min_similarity
  order by c.embedding <=> query_embedding
  limit match_count;
end;
$$;

commit;
