import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import *
from nlp.inferencia import Classificador

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

clf = Classificador(MODELO_NLP_PASTA)

@app.post("/classify/text", response_model=ClassificacaoResponse)
def classify_text(req: TextoClassificacaoRequest):

    # texto curto demais (ou vazio após normalizar) não é classificado
    resultado = clf.classificar_longo(req.text) if len(req.text.split()) >= MIN_PALAVRAS else None
    if resultado is None:
        resultado = {"category": TEXTO_PEQUENO, "score": None}

    return {
        "modality": MODALIDADE_NLP,
        "category": resultado["category"],
        "score": resultado["score"],
        "model_version": MODELO_NLP_VERSION
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
