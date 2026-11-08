"""
Cliente Supabase compartilhado pelo backend.

O backend faz a própria autenticação (tabela `users` + JWT), então ele precisa
de uma chave que ignore o RLS: a chave secreta / service_role. Ela fica SÓ no
servidor (.env), nunca no site ou na extensão.

Variáveis (.env):
    SUPABASE_URL                 URL do projeto
    SUPABASE_SERVICE_ROLE_KEY    chave secreta (sb_secret_... ou service_role) - recomendada
    SUPABASE_KEY                 fallback (ex.: chave publishable/anon). Só funciona
                                 enquanto o RLS das tabelas estiver desligado.
"""
import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_KEY")
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_KEY) no .env"
    )

if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")):
    print(
        "[AVISO] Usando SUPABASE_KEY (provavelmente a chave pública). Com RLS ligado "
        "nas tabelas users/logs, as gravações vão falhar: configure "
        "SUPABASE_SERVICE_ROLE_KEY no .env."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def explicar_erro(e: Exception, acao: str) -> None:
    """Escreve no console do servidor o motivo real de uma falha no Supabase."""
    codigo = getattr(e, "code", None)
    print(f"[ERRO] {acao}: {e}")
    if codigo == "42501":
        print(
            "       -> bloqueado pelo RLS: o backend precisa da chave secreta "
            "(SUPABASE_SERVICE_ROLE_KEY no .env), não da chave pública."
        )


def verificar_conexao() -> bool:
    """Faz uma consulta mínima para confirmar que o banco responde."""
    try:
        supabase.table("users").select("id_user").limit(1).execute()
        print("[OK] Conexão com o Supabase estabelecida com sucesso!")
        return True
    except Exception as e:  # não derruba o servidor; só avisa
        print(f"[ERRO] Erro ao conectar com o Supabase: {e}")
        return False
