import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from app.auth import get_current_user
from app.database import explicar_erro, supabase
from app.schemas import LogCreate

router = APIRouter(prefix="/logs", tags=["logs"])


def salvar_log(log: LogCreate, id_user: str) -> dict:
    """Grava um log no banco e devolve a linha criada (usado também por /analyze)."""
    try:
        response = (
            supabase.table("logs")
            .insert({
                "id_log": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": str(log.url),
                "level": log.level,
                "reason": log.reason,
                "id_user": id_user
            })
            .execute()
        )
    except APIError as e:
        explicar_erro(e, "gravação de log")
        raise HTTPException(status_code=500, detail="Erro ao gravar log")

    if not response.data:
        raise HTTPException(status_code=500, detail="Erro ao gravar log")
    return response.data[0]


def listar_logs(id_user: str, level: str | None, limit: int, offset: int) -> dict:
    query = (
        supabase.table("logs")
        .select("*")
        .eq("id_user", id_user)
        .order("timestamp", desc=True)
    )
    if level:
        query = query.eq("level", level)

    response = query.range(offset, offset + limit - 1).execute()
    return {"logs": response.data, "limit": limit, "offset": offset}


@router.post("", status_code=201)
def create_log(
    log: LogCreate,
    user=Depends(get_current_user)
):

    return {
        "message": "Log cadastrado com sucesso",
        "log": salvar_log(log, user["id_user"])
    }


@router.get("")
def get_logs(
    level: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user)
):
    """Logs do usuário autenticado (o id vem do token, nunca do cliente)."""
    return listar_logs(user["id_user"], level, limit, offset)


@router.get("/user/{id_user}")
def get_logs_do_usuario(
    id_user: UUID,
    level: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user)
):
    """Logs de um usuário específico: só o próprio usuário pode consultar."""
    if str(id_user) != str(user["id_user"]):
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para ver os logs deste usuário"
        )
    return listar_logs(str(id_user), level, limit, offset)


# ESTATÍSTICAS
# precisa vir ANTES de /{id_log}: senão "stats" é lido como um id de log
@router.get("/stats")
def get_log_stats(user=Depends(get_current_user)):

    response = (
        supabase.table("logs")
        .select("level")
        .eq("id_user", user["id_user"])
        .execute()
    )

    logs = response.data

    stats = {
        "total": len(logs),
        "by_level": {}
    }

    for log in logs:
        level = log["level"]

        stats["by_level"][level] = (
            stats["by_level"].get(level, 0) + 1
        )

    return stats


@router.get("/{id_log}")
def get_log(
    id_log: UUID,
    user=Depends(get_current_user)
):

    response = (
        supabase.table("logs")
        .select("*")
        .eq("id_log", str(id_log))
        .eq("id_user", user["id_user"])
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Log não encontrado"
        )

    return response.data[0]


@router.delete("/{id_log}")
def delete_log(
    id_log: UUID,
    user=Depends(get_current_user)
):

    response = (
        supabase.table("logs")
        .delete()
        .eq("id_log", str(id_log))
        .eq("id_user", user["id_user"])
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Log não encontrado"
        )

    return {
        "message": "Log excluído com sucesso"
    }
