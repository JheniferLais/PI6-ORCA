import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import *

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/classify/text")
def classify_text(req: TextoClassificacaoRequest):

    # verifica se o texto tem tamanho minimo
    if len(req.text.split()) < MIN_PALAVRAS:
        return {
            "modality": MODALIDADE_NLP,
            "category": CATEGORIA_NAO_DEFINIDA,
            "score": None,
            "model_version": MODELO_NLP_VERSION
        }

    # classifica baseado na IA
    categoria, score = classificar_texto(req.text)

    # retorna o valor da IA
    return {
        "modality": MODALIDADE_NLP,
        "category": categoria,
        "score": score,
        "model_version": MODELO_NLP_VERSION
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)