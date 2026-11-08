from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import verificar_conexao
from app.routes.analise import carregar_ia_imagem, router as analise_router
from app.routes.auth import router as auth_router
from app.routes.logs import router as logs_router
from nlp.nlp_router import router as nlp_router



@asynccontextmanager
async def lifespan(_app: FastAPI):
    verificar_conexao()
    carregar_ia_imagem()  # carrega o modelo de imagem na subida, não na primeira requisição
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Orca API",
    description="API de controle parental e gerenciamento de logs",
    version="1.0.0"
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)  # /auth/register, /auth/login, /auth/me
app.include_router(logs_router)  # /logs, /logs/stats, /logs/user/{id_user}, /logs/{id_log}

# app.include_router(nlp_router)   # POST /classify/

# app.include_router(img_router)   # POST /classify/img
app.include_router(analise_router)  # POST /analyze (texto + imagem -> log)



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
