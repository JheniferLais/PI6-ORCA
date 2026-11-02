from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.database import supabase
from app.schemas import LogCreate

router = APIRouter(prefix="/logs", tags=["logs"])


def salvar_log(log: LogCreate, id_user: str) -> dict:
    """Grava um log no banco e devolve a linha criada (usado também por /analyze)."""
    response = (
        supabase.table("logs")
        .insert({
            "url": str(log.url),
            "level": log.level,
            "reason": log.reason,
            "id_user": id_user
        })
        .execute()
    )
    return response.data[0]


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

    query = (
        supabase.table("logs")
        .select("*")
        .eq("id_user", user["id_user"])
        .order("timestamp", desc=True)
    )

    if level:
        query = query.eq("level", level)

    response = (
        query.range(offset, offset + limit - 1)
        .execute()
    )

    return {
        "logs": response.data,
        "limit": limit,
        "offset": offset
    }


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
    id_log: str,
    user=Depends(get_current_user)
):

    response = (
        supabase.table("logs")
        .select("*")
        .eq("id_log", id_log)
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
    id_log: str,
    user=Depends(get_current_user)
):

    response = (
        supabase.table("logs")
        .delete()
        .eq("id_log", id_log)
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
