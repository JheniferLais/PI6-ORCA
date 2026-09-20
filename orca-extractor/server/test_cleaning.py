"""
Testes rápidos do server/cleaning.py.

Rodar com:
    pytest test_cleaning.py -v
"""
from cleaning import clean_images, clean_text


def test_remove_menu_repetido():
    """Linhas curtas que se repetem 3+ vezes (menu/rodapé) devem sumir, mas
    o conteúdo principal (o parágrafo, que só aparece 1 vez) deve continuar.
    Repare que o menu aparece 3 vezes aqui — com só 2, a regra não considera
    boilerplate ainda (ver BOILERPLATE_MIN_REPEATS em cleaning.py)."""
    texto = """Menu
            Início
            Sobre
            Contato
            Menu
            Início
            Sobre
            Contato
            Este é o parágrafo principal da página, com informação de verdade que
            interessa para a classificação de conteúdo.
            Menu
            Início
            Sobre
            Contato"""

    resultado = clean_text(texto)

    assert "parágrafo principal" in resultado.text
    assert "Menu" not in resultado.text
    assert resultado.discarded is False


def test_texto_curto_e_descartado():
    """Texto muito curto (ex.: página quase só com imagem) deve ser marcado
    como descartado, para não ir pro classificador à toa."""
    resultado = clean_text("Oi.")

    assert resultado.discarded is True
    assert resultado.discard_reason == "texto_curto_demais"


def test_texto_gigante_e_truncado():
    """Texto maior que o limite deve ser cortado, não simplesmente rejeitado."""
    texto_gigante = "palavra de verdade repetida bastante. " * 1000  # bem maior que 20_000 chars

    resultado = clean_text(texto_gigante)

    assert resultado.discarded is False
    assert len(resultado.text) <= 20_000


def test_espacos_e_linhas_sao_normalizados():
    texto = "Olá     mundo!\n\n\n\n\nTudo   bem?   "

    resultado = clean_text(texto)

    assert "     " not in resultado.text  # sem espaços múltiplos
    assert "\n\n\n" not in resultado.text  # sem 3+ linhas em branco seguidas


def test_deteccao_de_idioma_portugues():
    """Só passa se o pacote langdetect estiver instalado (pip install -r
    requirements.txt). Sem ele, cleaning.py devolve language=None de propósito
    em vez de quebrar — então esse teste é pulado nesse caso."""
    import pytest
    from cleaning import detect as langdetect_disponivel

    if langdetect_disponivel is None:
        pytest.skip("langdetect não instalado neste ambiente")

    texto = (
        "Este texto está escrito em português e deveria ser identificado "
        "corretamente pelo detector de idioma como tal, com bastante confiança."
    )

    resultado = clean_text(texto)

    assert resultado.language == "pt"


def test_imagens_duplicadas_sao_removidas():
    imagens = [
        {"src": "https://site.com/logo.png", "alt": "logo", "width": 50, "height": 50},
        {"src": "https://site.com/logo.png", "alt": "logo", "width": 200, "height": 200},
        {"src": "https://site.com/foto.jpg", "alt": None, "width": 800, "height": 600},
    ]

    resultado = clean_images(imagens)

    # a logo repetida virou 1 só (a de maior resolução), + a foto = 2 no total
    assert len(resultado) == 2
    logo = next(img for img in resultado if img.src.endswith("logo.png"))
    assert logo.width == 200  # ficou com a maior resolução, não a primeira que apareceu


def test_imagens_sem_repeticao_ficam_todas():
    imagens = [
        {"src": "https://site.com/a.jpg", "alt": None, "width": 300, "height": 300},
        {"src": "https://site.com/b.jpg", "alt": None, "width": 300, "height": 300},
    ]

    resultado = clean_images(imagens)

    assert len(resultado) == 2