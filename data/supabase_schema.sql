-- Supabase スキーマ例（記憶保存を有効化するための最低限の定義）
-- 実行場所: Supabase SQL Editor など

-- 必要な拡張
create extension if not exists "vector";
create extension if not exists "pgcrypto";

-- 短期記憶（会話ログ）
create table if not exists public.short_term_memory (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  role text not null,
  content text not null,
  turn_number int not null default 0,
  session_id uuid not null,
  created_at timestamp with time zone default now()
);
create index if not exists idx_stm_user_session on public.short_term_memory (user_id, session_id);

-- 中期記憶（要約）
create table if not exists public.mid_term_memory (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  summary text not null,
  importance double precision not null default 0.5,
  source_session_id uuid not null,
  turn_range text not null,
  created_at timestamp with time zone default now()
);
create index if not exists idx_mtm_user on public.mid_term_memory (user_id);
create index if not exists idx_mtm_importance on public.mid_term_memory (importance desc);

-- 長期記憶（ベクトル検索）
create table if not exists public.long_term_memory (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  content text not null,
  memory_type text not null default 'fact',
  importance double precision not null default 0.5,
  source_mid_term_id uuid,
  embedding vector(1536),
  created_at timestamp with time zone default now(),
  last_accessed_at timestamp with time zone default now()
);
create index if not exists idx_ltm_user on public.long_term_memory (user_id);
create index if not exists idx_ltm_importance on public.long_term_memory (importance desc);
-- pgvector の近似検索インデックス（リスト数はデータ量に応じて調整）
create index if not exists idx_ltm_embedding on public.long_term_memory using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ベクトル検索用RPC
create or replace function public.match_long_term_memory(
  query_embedding vector(1536),
  match_user_id text,
  match_count int default 5,
  min_importance float default 0.0
) returns table (
  id uuid,
  user_id text,
  content text,
  memory_type text,
  importance float,
  source_mid_term_id uuid,
  created_at timestamp with time zone,
  last_accessed_at timestamp with time zone,
  distance float
) language sql stable as $$
  select
    ltm.id,
    ltm.user_id,
    ltm.content,
    ltm.memory_type,
    ltm.importance,
    ltm.source_mid_term_id,
    ltm.created_at,
    ltm.last_accessed_at,
    ltm.embedding <=> query_embedding as distance
  from public.long_term_memory ltm
  where ltm.user_id = match_user_id
    and ltm.importance >= min_importance
    and ltm.embedding is not null
  order by ltm.embedding <=> query_embedding
  limit match_count;
$$;

-- ※PostgreSQLでは SELECT トリガーが使えないためアクセス時刻更新はコード側で行う
-- 必要ならアプリ側で UPDATE を発行するか、別途適切なイベント（INSERT/UPDATE）でトリガーを作成してください。
