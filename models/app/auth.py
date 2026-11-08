import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from app.database import supabase

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

if not JWT_SECRET:
    raise RuntimeError("Configure JWT_SECRET no .env")

# Argon2 (recomendado pelo pwdlib)
password_hash = PasswordHash.recommended()
# hash qualquer, usado para gastar o mesmo tempo quando o usuário não existe
# (evita descobrir e-mails cadastrados pelo tempo de resposta)
_HASH_FALSO = password_hash.hash("senha-que-nao-existe")

security = HTTPBearer(auto_error=False)

USER_PUBLIC_COLUMNS = "id_user, name, email"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        password_hash.verify(password, _HASH_FALSO)
        return False
    try:
        return password_hash.verify(password, hashed)
    except Exception:
        # hash em formato desconhecido (ex.: senha antiga gravada em texto puro)
        return False


def create_access_token(id_user: str) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(id_user),
        "iat": agora,
        "exp": agora + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _nao_autorizado(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    """Dependência das rotas protegidas: devolve {id_user, name, email}."""
    if credentials is None:
        raise _nao_autorizado("Não autenticado")

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _nao_autorizado("Token expirado")
    except jwt.InvalidTokenError:
        raise _nao_autorizado("Token inválido")

    id_user = payload.get("sub")
    if not id_user:
        raise _nao_autorizado("Token inválido")

    response = (
        supabase.table("users")
        .select(USER_PUBLIC_COLUMNS)
        .eq("id_user", id_user)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise _nao_autorizado("Usuário não encontrado")

    return response.data[0]
