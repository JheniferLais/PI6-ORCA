r"""
Teste ponta a ponta de cadastro, login e logs CONTRA O SUPABASE REAL.

Cria dois usuários temporários (A e B), grava um log, confere no banco que ele
está lá com o id_user certo, testa o isolamento entre usuários e no fim apaga
tudo o que criou.

    cd models
    .venv\Scripts\python.exe scripts\testar_supabase.py

Precisa de SUPABASE_SERVICE_ROLE_KEY no .env (com RLS ligado, a chave pública
não consegue gravar).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import supabase  # noqa: E402
from app.routes.auth import router as auth_router  # noqa: E402
from app.routes.logs import router as logs_router  # noqa: E402

app = FastAPI()
app.include_router(auth_router)
app.include_router(logs_router)
c = TestClient(app)

falhas = 0
criados: list[str] = []


def check(nome, ok, extra=""):
    global falhas
    falhas += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {nome} {extra}")


def status(nome, r, esperado):
    check(nome, r.status_code == esperado, f"-> {r.status_code} {str(r.json())[:100]}")
    return r


tag = uuid.uuid4().hex[:8]
A = {"name": "Teste A", "email": f"teste_a_{tag}@exemplo.com", "password": "SenhaForte123"}
B = {"name": "Teste B", "email": f"teste_b_{tag}@exemplo.com", "password": "OutraSenha456"}

try:
    # 1. cadastro
    r = status("1. cadastro do usuário A", c.post("/auth/register", json=A), 201)
    if r.status_code != 201:
        raise SystemExit("Cadastro falhou; veja a mensagem [ERRO] acima (RLS/chave?).")
    id_a = r.json()["user"]["id_user"]
    criados.append(id_a)
    r = status("1. cadastro do usuário B", c.post("/auth/register", json=B), 201)
    id_b = r.json()["user"]["id_user"]
    criados.append(id_b)
    status("1. e-mail duplicado", c.post("/auth/register", json=A), 409)
    status("1. e-mail duplicado (maiúsculas)", c.post("/auth/register", json={**A, "email": A["email"].upper()}), 409)
    status("1. e-mail inválido", c.post("/auth/register", json={**A, "email": "sem-arroba"}), 422)
    linha = supabase.table("users").select("*").eq("id_user", id_a).execute().data
    check("1. usuário A está na tabela users", len(linha) == 1)
    check("1. e-mail gravado na coluna email", linha[0].get("email") == A["email"])
    check("1. senha gravada com hash (argon2)", linha[0]["password"].startswith("$argon2"))

    # 2 e 3. login
    r = status("2. login válido", c.post("/auth/login", json={"email": A["email"], "password": A["password"]}), 200)
    ha = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = c.post("/auth/login", json={"email": B["email"], "password": B["password"]})
    hb = {"Authorization": f"Bearer {r.json()['access_token']}"}
    status("3. login com senha errada", c.post("/auth/login", json={"email": A["email"], "password": "errada123"}), 401)
    status("3. login de usuário inexistente", c.post("/auth/login", json={"email": f"nao_{tag}@exemplo.com", "password": "x"}), 401)
    status("   /auth/me", c.get("/auth/me", headers=ha), 200)

    # 4 e 5. cadastro de log
    r = status("4. cadastro de log (A)", c.post("/logs", json={"url": "https://exemplo.com/p", "level": "alerta", "reason": "Conteúdo sexual"}, headers=ha), 201)
    id_log = r.json()["log"]["id_log"]
    status("4. cadastro de log sem token", c.post("/logs", json={"url": "https://x.com", "level": "a", "reason": "r"}), 401)
    linha = supabase.table("logs").select("*").eq("id_log", id_log).execute().data
    check("4. log está na tabela logs", len(linha) == 1)
    check("5. id_user do log == usuário autenticado", bool(linha) and linha[0]["id_user"] == id_a)

    # 6. consulta e isolamento
    r = status("6. A lista os próprios logs", c.get("/logs", headers=ha), 200)
    check("6. A vê 1 log", len(r.json()["logs"]) == 1)
    r = status("6. B lista os próprios logs", c.get("/logs", headers=hb), 200)
    check("6. B não vê o log de A", len(r.json()["logs"]) == 0)
    status("6. A consulta /logs/user/A", c.get(f"/logs/user/{id_a}", headers=ha), 200)
    status("6. B tenta /logs/user/A", c.get(f"/logs/user/{id_a}", headers=hb), 403)
    status("6. B tenta ler o log de A", c.get(f"/logs/{id_log}", headers=hb), 404)
    status("6. B tenta apagar o log de A", c.delete(f"/logs/{id_log}", headers=hb), 404)
finally:
    if criados:
        supabase.table("logs").delete().in_("id_user", criados).execute()
        supabase.table("users").delete().in_("id_user", criados).execute()
        print("limpeza: usuários e logs de teste removidos")

print("\nTUDO OK" if falhas == 0 else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
