"""Cache LRU simples e seguro para várias threads."""
import threading
from collections import OrderedDict
from typing import Optional


class CacheLRU:
    """Guarda até 'tamanho' entradas; ao estourar, descarta a menos usada."""

    def __init__(self, tamanho: int):
        self.tamanho = tamanho
        self._dados: "OrderedDict[str, dict]" = OrderedDict()
        self._trava = threading.Lock()

    def obter(self, chave: str) -> Optional[dict]:
        with self._trava:
            valor = self._dados.get(chave)
            if valor is not None:
                self._dados.move_to_end(chave)
            return valor

    def guardar(self, chave: str, valor: dict) -> None:
        with self._trava:
            self._dados[chave] = valor
            self._dados.move_to_end(chave)
            while len(self._dados) > self.tamanho:
                self._dados.popitem(last=False)

    def __len__(self) -> int:
        return len(self._dados)
