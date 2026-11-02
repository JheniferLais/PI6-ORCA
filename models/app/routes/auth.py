from fastapi import APIRouter, Depends, HTTPException

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import supabase
from app.schemas import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(user: UserCreate):

    existing = (
        supabase.table("users")
        .select("id_user")
        .eq("identificador", user.identificador)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="Identificador já cadastrado"
        )

    response = (
        supabase.table("users")
        .insert({
            "identificador": user.identificador,
            "senha": hash_password(user.senha)
        })
        .execute()
    )

    created_user = response.data[0]

    return {
        "message": "Usuário cadastrado com sucesso",
        "user": {
            "id_user": created_user["id_user"],
            "identificador": created_user["identificador"]
        }
    }


@router.post("/login")
def login(user: UserLogin):

    response = (
        supabase.table("users")
        .select("id_user, identificador, senha")
        .eq("identificador", user.identificador)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=401,
            detail="Identificador ou senha inválidos"
        )

    db_user = response.data[0]

    if not verify_password(user.senha, db_user["senha"]):
        raise HTTPException(
            status_code=401,
            detail="Identificador ou senha inválidos"
        )

    token = create_access_token(db_user["id_user"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id_user": db_user["id_user"],
            "identificador": db_user["identificador"]
        }
    }


@router.get("/me")
def get_me(user=Depends(get_current_user)):

    return {
        "id_user": user["id_user"],
        "identificador": user["identificador"]
    }
