-- Sessões persistentes (refresh token) e monitoramento por usuário.
-- Rodar no Supabase: SQL Editor -> New query -> colar -> Run. Pode rodar mais de uma vez.
--
-- Usado por models/app/sessoes.py, models/app/auth.py e models/app/routes/monitoramento.py.

-- 1. Monitoramento ligado/desligado (o botão do painel de logs).
--    Começa desligado: o usuário liga quando quiser que a extensão analise as páginas.
alter table public.users
  add column if not exists monitoring_enabled boolean not null default false;

-- 2. Uma linha por login (site) ou por extensão vinculada.
--    refresh_hash = SHA-256 do segredo do refresh token (o token em si nunca é gravado).
--    revoked_at preenchido = sessão encerrada (logout ou refresh token reutilizado).
create table if not exists public.sessions (
  id_session    uuid primary key default gen_random_uuid(),
  id_user       uuid not null references public.users (id_user) on delete cascade,
  client        text not null check (client in ('site', 'extension')),
  refresh_hash  text not null,
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz not null default now(),
  expires_at    timestamptz not null,
  revoked_at    timestamptz
);

create index if not exists sessions_id_user_idx on public.sessions (id_user);

-- 3. Só o backend (chave secreta) acessa: sem políticas, a chave pública não lê nem grava.
alter table public.sessions enable row level security;
revoke all on public.sessions from anon, authenticated;

-- Opcional, para limpar de tempos em tempos as sessões que já não valem:
--   delete from public.sessions
--   where revoked_at is not null or expires_at < now() - interval '7 days';
