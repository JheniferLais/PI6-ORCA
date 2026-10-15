"""
Carrega um modelo salvo pelo treino.py (ex.: artifacts/nlp-v1) e classifica textos.

Aplica a MESMA normalização do treino (normalizacao.py). Não faz parte do
endpoint /classify/text, que fica fora do escopo do S2-03: esta classe só
permite recarregar o modelo salvo e servirá de base para a integração futura.
Regras de texto mínimo/vazio ("indefinido") pertencem ao endpoint.

Uso:
    from inferencia import Classificador
    clf = Classificador("models/nlp/artifacts/nlp-v1")
    clf.classificar("texto")  # [{'category': ..., 'score': ..., 'model_version': 'nlp-v1', ...}]
"""
import json
from pathlib import Path

import normalizacao as norm


class Classificador:
    def __init__(self, pasta):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.pasta = Path(pasta)
        arq = self.pasta / "orca_model.json"
        if not arq.exists():
            raise FileNotFoundError(f"{arq} não existe: treino incompleto ou pasta errada")
        self.meta = json.loads(arq.read_text(encoding="utf-8"))
        if self.meta["normalizacao"]["versao"] != norm.VERSAO:
            raise RuntimeError(f"modelo treinado com {self.meta['normalizacao']['versao']}, "
                               f"mas normalizacao.py está em {norm.VERSAO}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.pasta)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(self.pasta).eval()
        id2label = {int(i): c for i, c in self.modelo.config.id2label.items()}
        self.classes = [id2label[i] for i in range(len(id2label))]
        if self.classes != self.meta["classes"]:
            raise RuntimeError(f"mapa de rótulos do modelo {self.classes} difere do "
                               f"registrado {self.meta['classes']}")
        self.max_length = self.meta["max_length"]
        self.model_version = self.meta["id"]

    def classificar(self, textos):
        if isinstance(textos, str):
            textos = [textos]
        codificado = self.tokenizer([norm.normalizar(t) for t in textos], truncation=True,
                                    max_length=self.max_length, padding=True, return_tensors="pt")
        with self._torch.no_grad():
            probs = self._torch.softmax(self.modelo(**codificado).logits, dim=-1)
        resultados = []
        for linha in probs:
            i = int(linha.argmax())
            resultados.append({
                "category": self.classes[i],
                "score": float(linha[i]),
                "model_version": self.model_version,
                "probabilidades": {c: float(p) for c, p in zip(self.classes, linha)},
            })
        return resultados
