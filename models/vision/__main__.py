"""
Classificador de imagens do ORCA. Rode a partir de models/:

  python -m vision dados                       1. monta o dataset (baixa as fontes de data/fontes.json)
  python -m vision dados --inspecionar         1b. só mostra as pastas de cada fonte, sem montar
  python -m vision avaliar                     2. avalia o modelo no conjunto de teste
  python -m vision avaliar --divisao validacao --limite 200     conferência rápida numa amostra
  python -m vision                             3. sobe o servidor para a extensão (localhost:8000)
  python -m vision servir                      (o mesmo que acima)
"""
import argparse
import sys
from pathlib import Path

if not __package__:
    # executado como arquivo (python vision/__main__.py, botão Run da IDE): torna o pacote importável
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    p = argparse.ArgumentParser(prog="python -m vision", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("servir", help="sobe o servidor de imagens (padrão)")
    sub.add_parser("dados", add_help=False,
                   help="monta o dataset; aceita as opções de vision/data/pipeline.py (veja --help)")
    a = sub.add_parser("avaliar", help="matriz de confusão e métricas no dataset")
    a.add_argument("--divisao", choices=["treino", "validacao", "teste"], default="teste")
    a.add_argument("--limite", type=int, help="usa só uma amostra estratificada (conferência rápida)")
    a.add_argument("--pasta", help="pasta do dataset; padrão: vision/data/datasets")
    a.add_argument("--seed", type=int, default=42)
    args, resto = p.parse_known_args()

    if args.cmd == "dados":
        from vision.data.pipeline import main as montar
        montar(resto)
        return
    if resto:
        p.error(f"argumentos desconhecidos: {' '.join(resto)}")

    if args.cmd == "avaliar":
        from vision.avaliacao import avaliar
        try:
            avaliar(args.divisao, args.pasta, args.limite, args.seed)
        except (ValueError, FileNotFoundError) as erro:
            sys.exit(f"ERRO: {erro}")
    else:
        import uvicorn
        from vision.pipeline import HOST, PORTA, app
        uvicorn.run(app, host=HOST, port=PORTA)


if __name__ == "__main__":
    main()
