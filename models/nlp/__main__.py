"""
Classificador de texto do ORCA. Rode a partir de models/:

  python nlp/data/pipeline.py                  1. gera os datasets (baixa as fontes)
  python -m nlp dados                          2. confere CSVs, colisões e pesos de classe
  python -m nlp treinar --teste-rapido         3. valida o fluxo em minutos (não é resultado)
  python -m nlp treinar                        4. treino completo (horas em CPU)
  python -m nlp avaliar                        5. avalia o modelo salvo na validação
  python -m nlp avaliar --divisao teste        6. avaliação final, uma vez, no teste
"""
import argparse
import sys
from pathlib import Path

if not __package__:
    # executado como arquivo (python nlp/__main__.py, botão Run da IDE): torna o pacote importável
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nlp import dados as dd
from nlp.treino import CONFIG_PADRAO, PASTA_ARTIFACTS, carregar_config


def mostrar_dados(config):
    d = dd.preparar_dados()
    c = d["colisoes"]
    print("Arquivos:")
    for nome, info in d["arquivos"].items():
        print(f"  {nome}: {info.get('linhas', '-')} linhas, sha256_lf={info['sha256_lf'][:16]}...")
    print("\nColisões após a normalização:")
    print(f"  textos em mais de uma divisão: {c['chaves_em_mais_de_uma_divisao']} "
          f"(com rótulo divergente: {c['chaves_com_rotulo_divergente']})")
    for div in ("treino", "validacao"):
        print(f"  removidos de {div}: {c['removidos'][div]['total']} {c['removidos'][div]['por_motivo']}")
    print(f"  linhas efetivas: {c['linhas_efetivas']}")
    pesos = dd.calcular_pesos(d["treino"]["y"], config["pesos_classe"])
    print(f"\nPesos de classe ({pesos['formula']}, N={pesos['N']}):")
    for classe in dd.CLASSES:
        print(f"  {classe}: n={pesos['contagens'][classe]}  peso={pesos['pesos'][classe]:.6f}")


def main():
    p = argparse.ArgumentParser(prog="python -m nlp", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(CONFIG_PADRAO), help="configuração do experimento")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("dados", help="confere CSVs, colisões e pesos de classe (sem torch)")
    t = sub.add_parser("treinar", help="fine-tuning; salva em artifacts/<versao>")
    t.add_argument("--teste-rapido", action="store_true",
                   help="amostra pequena e 1 época, em artifacts/<versao>-teste")
    t.add_argument("--forcar", action="store_true",
                   help="arquiva o modelo existente em vez de recusar")
    a = sub.add_parser("avaliar", help="matriz de confusão e métricas do modelo salvo")
    a.add_argument("--divisao", choices=["validacao", "teste"], default="validacao")
    a.add_argument("--teste-rapido", action="store_true", help="avalia artifacts/<versao>-teste")
    a.add_argument("--limite", type=int, help="usa só uma amostra estratificada (conferência rápida)")
    args = p.parse_args()
    if args.cmd is None:
        return

    try:
        config = carregar_config(args.config)
        if args.cmd == "dados":
            mostrar_dados(config)
        elif args.cmd == "treinar":
            from nlp.treino import treinar
            treinar(args.config, args.teste_rapido, args.forcar)
        else:
            from nlp.avaliacao import avaliar
            pasta = PASTA_ARTIFACTS / (config["versao"] + ("-teste" if args.teste_rapido else ""))
            avaliar(pasta, args.divisao, args.limite, config["hiperparametros"]["seed"])
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as erro:
        sys.exit(f"ERRO: {erro}")


if __name__ == "__main__":
    main()
