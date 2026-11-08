import uuid

from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from app.auth import (
    USER_PUBLIC_COLUMNS,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import explicar_erro, supabase
from app.schemas import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])

CREDENCIAIS_INVALIDAS = "E-mail ou senha inválidos"
EMAIL_JA_CADASTRADO = "E-mail já cadastrado"


def _publico(user: dict) -> dict:
    return {"id_user": user["id_user"], "name": user.get("name"), "email": user["email"]}


@router.post("/register", status_code=201)
def register(user: UserCreate):
    existing = (
        supabase.table("users")
        .select("id_user")
        .eq("email", user.email)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail=EMAIL_JA_CADASTRADO)

    novo = {
        "id_user": str(uuid.uuid4()),
        "name": user.name,
        "email": user.email,
        "password": hash_password(user.password),
    }

    try:
        response = supabase.table("users").insert(novo).execute()
    except APIError as e:
        if e.code == "23505":  # unique_violation (cadastro simultâneo)
            raise HTTPException(status_code=409, detail=EMAIL_JA_CADASTRADO)
        explicar_erro(e, "cadastro de usuário")
        raise HTTPException(status_code=500, detail="Erro ao cadastrar usuário")

    if not response.data:
        raise HTTPException(status_code=500, detail="Erro ao cadastrar usuário")

    return {"message": "Usuário cadastrado com sucesso", "user": _publico(response.data[0])}


@router.post("/login")
def login(user: UserLogin):
    response = (
        supabase.table("users")
        .select(f"{USER_PUBLIC_COLUMNS}, password")
        .eq("email", user.email)
        .limit(1)
        .execute()
    )
    db_user = response.data[0] if response.data else None

    # verifica sempre (mesmo sem usuário) para não vazar quem existe pelo tempo
    if not verify_password(user.password, db_user["password"] if db_user else None) or not db_user:
        raise HTTPException(status_code=401, detail=CREDENCIAIS_INVALIDAS)

    return {
        "access_token": create_access_token(db_user["id_user"]),
        "token_type": "bearer",
        "user": _publico(db_user),
    }


@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return _publico(user)
