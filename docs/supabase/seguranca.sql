-- Rodar no Supabase: SQL Editor -> New query -> colar -> Run.
--
-- O backend (models/) faz a autenticação sozinho (tabela users + JWT) e acessa
-- o banco com a chave secreta (SUPABASE_SERVICE_ROLE_KEY), que ignora o RLS.
-- Ligando o RLS SEM políticas, a chave pública (publishable/anon) deixa de
-- conseguir ler ou gravar users/logs: senhas e logs só passam pela API.
--
-- ATENÇÃO: depois de rodar isto, o backend PRECISA da SUPABASE_SERVICE_ROLE_KEY
-- no .env; com a chave pública ele não consegue mais acessar as tabelas.

-- E-mail único (impede cadastro duplicado mesmo em requisições simultâneas).
-- O backend grava o e-mail sempre em minúsculas e sem espaços.
create unique index if not exists users_email_key
  on public.users (email);

-- Defaults no banco (o backend já envia os valores; isto é só uma rede de segurança)
alter table public.users alter column id_user  set default gen_random_uuid();
alter table public.logs  alter column id_log   set default gen_random_uuid();
alter table public.logs  alter column timestamp set default now();

-- Busca dos logs por usuário, mais recentes primeiro
create index if not exists logs_id_user_timestamp_idx
  on public.logs (id_user, timestamp desc);

-- Row Level Security: nenhum acesso direto pelas chaves públicas
alter table public.users enable row level security;
alter table public.logs  enable row level security;

revoke all on public.users from anon, authenticated;
revoke all on public.logs  from anon, authenticated;
