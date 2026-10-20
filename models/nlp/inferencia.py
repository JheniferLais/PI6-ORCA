"""
Carrega um modelo salvo pelo treino (ex.: artifacts/nlp-v1) e classifica textos,
aplicando a MESMA normalização do treino (normalizacao.py).

    from nlp.inferencia import Classificador
    clf = Classificador("nlp/artifacts/nlp-v1")
    clf.classificar(["texto"])   # [{'category', 'score', 'probabilidades'}]  (avaliação)
    clf.classificar_longo("...") # {'category': 'odio', 'score': 0.97}  (servidor)
"""
import json
from pathlib import Path

from . import normalizacao as norm

CLASSE_SEGURA = "seguro"
LOTE = 32


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

    def _probabilidades(self, codificado):
        with self._torch.no_grad():
            return self._torch.softmax(self.modelo(**codificado).logits, dim=-1)

    def classificar(self, textos):
        """Um resultado por texto. Textos maiores que max_length são truncados,
        como no treino: é o que a avaliação do modelo mede."""
        if isinstance(textos, str):
            textos = [textos]
        codificado = self.tokenizer([norm.normalizar(t) for t in textos], truncation=True,
                                    max_length=self.max_length, padding=True, return_tensors="pt")
        resultados = []
        for linha in self._probabilidades(codificado):
            i = int(linha.argmax())
            resultados.append({
                "category": self.classes[i],
                "score": float(linha[i]),
                "probabilidades": {c: float(p) for c, p in zip(self.classes, linha)},
            })
        return resultados

    def classificar_longo(self, texto):
        """Uma categoria para um texto de qualquer tamanho (ex.: uma página).

        O texto é dividido em janelas de max_length tokens (as vizinhas repetem
        1/4 da janela, para um trecho não ser cortado ao meio) e cada janela é
        classificada. O texto vale pela janela mais grave: se alguma janela não
        é 'seguro', vence a de maior score; senão é 'seguro' com o score da
        janela menos confiante. Texto vazio após normalizar devolve None."""
        texto = norm.normalizar(texto)
        if not texto:
            return None
        janelas = self.tokenizer(texto, truncation=True, max_length=self.max_length,
                                 stride=self.max_length // 4, return_overflowing_tokens=True,
                                 padding=True, return_tensors="pt")
        janelas.pop("overflow_to_sample_mapping")
        probs = self._torch.cat([self._probabilidades({k: v[i:i + LOTE] for k, v in janelas.items()})
                                 for i in range(0, len(janelas["input_ids"]), LOTE)])
        scores, indices = probs.max(dim=-1)
        segura = self.classes.index(CLASSE_SEGURA)
        risco = indices != segura
        if risco.any():
            j = int(self._torch.where(risco, scores, -1.0).argmax())
        else:
            j = int(scores.argmin())
        return {"category": self.classes[int(indices[j])], "score": float(scores[j])}
