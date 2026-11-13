#!/usr/bin/env python3
"""Confere o Alinhamento Construtivo do plano: todo RA da seção 3 (Competências)
precisa ser avaliado na seção 4 (Metodologia e Avaliação) e trabalhado no
cronograma; e todo RA citado na seção 4 ou no cronograma precisa existir na 3.

Só biblioteca padrão do Python — sem pip install.

Uso:
    python3 verifica_ras.py dados.json
    python3 verifica_ras.py --demo

`dados.json` está no formato do extrator (`{"valores": ..., "linhas_repetir": ...}`),
o mesmo que `preencher_template.py` consome; aceita também a saída inteira de
`extrai_plano_existente.py` (`{"dados": ..., "avisos": ...}`). Lê
`linhas_repetir.IM_RA[].IM_RA`, `linhas_repetir.MET_RA[].MET_RA` e
`linhas_repetir.CRONO_PERIODO[].CRONO_RA`.

Saída JSON: `{"ras_secao3", "ras_secao4", "ras_cronograma", "orfaos", "avisos"}`.
Cada órfão é `{"ra", "falta_em": ["secao3"|"secao4"|"cronograma"]}`.

Por que existe: ninguém conferia isso à mão e RA sem avaliação ou sem aula
passa batido. O script nunca corrige nada nem decide pelo professor: toda
ambiguidade (texto sem RA reconhecível, seção vazia) vira item em `avisos`.
"""
import json
import re
import sys

ROTULOS = {"secao3": "seção 3", "secao4": "seção 4", "cronograma": "cronograma"}
RE_FAIXA = re.compile(r"RA\s*(\d+)\s*(?:a|à|até|-|–)\s*(?:RA\s*)?(\d+)", re.IGNORECASE)
RE_RA = re.compile(r"RA\s*(\d+)", re.IGNORECASE)
RE_TODOS = re.compile(r"\btodos\b", re.IGNORECASE)


def desmonta_ras(texto, ras_secao3=(), avisos=None):
    """Lista ordenada e sem repetição de RAs normalizados ("RA1") citados em
    `texto`. Entende "RA1, RA2 e RA3", "RA1/RA2", "RA 1", "ra3", "RA1 a RA3",
    "RA1-RA3". "Todos"/"Todos os RAs" expande para `ras_secao3`. Texto sem RA
    reconhecível devolve [] e acrescenta um aviso em `avisos` (se for lista)."""
    texto = texto or ""
    numeros = set()
    for ini, fim in RE_FAIXA.findall(texto):
        a, b = sorted((int(ini), int(fim)))
        numeros.update(range(a, b + 1))
    numeros.update(int(n) for n in RE_RA.findall(RE_FAIXA.sub(" ", texto)))
    ras = {f"RA{n}" for n in numeros}
    if RE_TODOS.search(texto):
        ras.update(ras_secao3)
    aviso = f"texto sem RA reconhecível: \"{' '.join(texto.split())}\""
    if not ras and avisos is not None and texto.strip() not in ("", "-", "–") and aviso not in avisos:
        avisos.append(aviso)
    return sorted(ras, key=lambda r: int(r[2:]))


def _ras_da_secao(linhas, campo, ras_secao3, avisos):
    ras = set()
    for linha in linhas or []:
        ras.update(desmonta_ras(linha.get(campo, ""), ras_secao3, avisos))
    return sorted(ras, key=lambda r: int(r[2:]))


def verifica_ras(dados):
    """Cruza as três seções. Devolve o dicionário de saída descrito no módulo."""
    lr = dados.get("linhas_repetir", {})
    avisos = []
    ras3 = _ras_da_secao(lr.get("IM_RA"), "IM_RA", (), avisos)
    ras4 = _ras_da_secao(lr.get("MET_RA"), "MET_RA", ras3, avisos)
    rasc = _ras_da_secao(lr.get("CRONO_PERIODO"), "CRONO_RA", ras3, avisos)
    secoes = {"secao3": ras3, "secao4": ras4, "cronograma": rasc}

    for chave, ras in secoes.items():
        if not ras:
            avisos.append(f"{ROTULOS[chave]} sem RA extraído")

    faltas = {}
    if ras3:
        for chave in ("secao4", "cronograma"):
            if not secoes[chave]:
                continue
            for ra in ras3:
                if ra not in secoes[chave]:
                    faltas.setdefault(ra, []).append(chave)
            for ra in secoes[chave]:
                if ra not in ras3:
                    faltas.setdefault(ra, []).append("secao3")
    orfaos = []
    for ra in sorted(faltas, key=lambda r: int(r[2:])):
        onde = sorted(set(faltas[ra]))
        orfaos.append({"ra": ra, "falta_em": onde})
        nomes = " e ".join(ROTULOS[o] for o in onde)
        if onde == ["secao3"]:
            avisos.append(f"{ra} é citado na seção 4 ou no cronograma mas não existe na seção 3")
        else:
            avisos.append(f"{ra} está na seção 3 mas falta na {nomes}")
    return {
        "ras_secao3": ras3,
        "ras_secao4": ras4,
        "ras_cronograma": rasc,
        "orfaos": orfaos,
        "avisos": avisos,
    }


def main():
    if len(sys.argv) != 2:
        print("uso: python3 verifica_ras.py dados.json | --demo", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        dados = json.load(f)
    if "dados" in dados:
        dados = dados["dados"]
    print(json.dumps(verifica_ras(dados), ensure_ascii=False, indent=2))


def _plano(im, met, crono):
    return {"linhas_repetir": {
        "IM_RA": [{"IM_RA": t} for t in im],
        "MET_RA": [{"MET_RA": t} for t in met],
        "CRONO_PERIODO": [{"CRONO_RA": t} for t in crono],
    }}


def demo():
    """python3 verifica_ras.py --demo"""
    assert desmonta_ras("RA1, RA2 e RA3") == ["RA1", "RA2", "RA3"]
    assert desmonta_ras("RA 2/ra3") == ["RA2", "RA3"]
    assert desmonta_ras("RA1 a RA3") == ["RA1", "RA2", "RA3"]
    assert desmonta_ras("RA1-RA3; RA2") == ["RA1", "RA2", "RA3"]
    assert desmonta_ras("Todos os RAs", ["RA1", "RA2", "RA3", "RA4"]) == ["RA1", "RA2", "RA3", "RA4"]
    av = []
    assert desmonta_ras("Aula expositiva", (), av) == [] and len(av) == 1, av

    # plano coerente
    r = verifica_ras(_plano(["RA1", "RA2"], ["RA1 e RA2"], ["RA1", "RA2", "Todos"]))
    assert r["orfaos"] == [] and r["avisos"] == [], r

    # RA3 sem avaliação
    r = verifica_ras(_plano(["RA1", "RA3"], ["RA1"], ["RA1", "RA3"]))
    assert r["orfaos"] == [{"ra": "RA3", "falta_em": ["secao4"]}], r
    assert any("RA3" in a for a in r["avisos"]), r

    # RA5 no cronograma sem existir na seção 3
    r = verifica_ras(_plano(["RA1"], ["RA1"], ["RA1", "RA5"]))
    assert r["orfaos"] == [{"ra": "RA5", "falta_em": ["secao3"]}], r

    # seção ausente: aviso, não órfão em massa
    r = verifica_ras(_plano(["RA1", "RA2"], [], ["RA1", "RA2"]))
    assert r["orfaos"] == [] and r["avisos"] == ["seção 4 sem RA extraído"], r

    print("demo ok — desmonta_ras e verifica_ras batem")


if __name__ == "__main__":
    if sys.argv[1:] == ["--demo"]:
        demo()
    else:
        main()
