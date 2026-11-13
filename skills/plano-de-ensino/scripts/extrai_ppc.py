#!/usr/bin/env python3
"""Lê o ANEXO A ("PLANOS DE ENSINO") do PPC do curso e extrai, por
disciplina, Período/Disciplina/Professor/CH/Ementa/Temas de
Estudo/Bibliografia Básica/Bibliografia Complementar/Justificativa —
fonte de verdade institucional pra popular esses campos automaticamente
em vez de o professor colar/redigitar (task "Análise do PPC" do backlog).

Entrada é o PPC já convertido de `.docx` pra Markdown via `markitdown`
(`markitdown PPC.docx > ppc.md`) — o `.docx` original tem ~32MB e não
compensa reabrir com `zipfile`/`ElementTree` como `extrai_plano_existente.py`
faz pro plano individual; o ANEXO A já sai em tabelas markdown limpas.

Cada campo do ANEXO A é uma linha de tabela própria, ex.:
`| **Ementa**:  texto... | | |` (3 colunas, só a 1ª preenchida). O rótulo
varia entre `**Rótulo**:`, `**Rótulo:**` (dois-pontos ora dentro ora fora
do negrito) e, em pelo menos 2 disciplinas (Mobile Development: Framework,
Management Science), **sem negrito nenhum** — `Bibliografia Complementar
(min. 5):` ou `JUSTIFICATIVA:` como texto puro, provavelmente perda de
formatação na digitação original do PPC, não na conversão. `_campo` casa
os três formatos pelo texto do rótulo, ignorando asteriscos. Campo ausente
(`Justificativa` falta em 1 das 44 disciplinas) ou vazio (`Professor` vazio
em 1 disciplina) não vira aviso por disciplina — só um aviso agregado no
fim, por campo.

Nunca decide sozinho quando a extração é ambígua: linha de tabela que não
casa nenhum rótulo conhecido é ignorada, não adivinhada.
"""
import json
import re
import sys

INICIO_ANEXO_A = re.compile(r"^#\s*ANEXO A\b")
FIM_ANEXO_A = re.compile(r"^#\s*ANEXO B\b")

ROTULOS = {
    "período": "PERIODO",
    "disciplina": "DISCIPLINA",
    "professor": "PROFESSOR",
    "ch (hr)": "CH_HR",
    "ch (ha)": "CH_HA",
    "ementa": "EMENTA",
    "temas de estudo": "TEMAS_ESTUDO",
    "temas de estudos": "TEMAS_ESTUDO",
    "bibliografia básica": "BIBLIOGRAFIA_BASICA",
    "bibliografia complementar": "BIBLIOGRAFIA_COMPLEMENTAR",
    "justificativa": "JUSTIFICATIVA",
}
# Mais longo primeiro: "temas de estudos" tem que casar antes de "temas de
# estudo" (prefixo), senão sobra um "s" solto no valor.
_ROTULOS_ORDENADOS = sorted(ROTULOS.items(), key=lambda kv: -len(kv[0]))

_SUFIXO_MIN = re.compile(r"^\(min\.\s*\d+\)\s*")


def _secao_anexo_a(linhas):
    """Todas as linhas -> só as do ANEXO A (entre o heading e o ANEXO B
    seguinte). Levanta ValueError se não achar o heading — melhor falhar
    alto do que devolver lista vazia silenciosamente."""
    inicio = next((i for i, l in enumerate(linhas) if INICIO_ANEXO_A.match(l)), None)
    if inicio is None:
        raise ValueError("heading 'ANEXO A' não encontrado no markdown")
    fim = next((i for i, l in enumerate(linhas[inicio:], inicio) if FIM_ANEXO_A.match(l)), len(linhas))
    return linhas[inicio:fim]


def _celulas(linha):
    """Linha de tabela markdown -> lista de células (sem os `|` das bordas)."""
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _campo(celula):
    """`**Rótulo**: valor`, `**Rótulo:** valor` ou `Rótulo: valor` (sem
    negrito nenhum) -> (chave normalizada, valor) ou (None, None) se a
    célula não for um campo reconhecido (célula vazia, cabeçalho de
    período tipo `**1º PERÍODO**`, etc). Casa pelo texto do rótulo em vez
    de depender de `**` estar presente — 2 disciplinas do PPC perdem o
    negrito do rótulo por completo."""
    sem_asteriscos = celula.lstrip("*").strip()
    for rotulo, chave in _ROTULOS_ORDENADOS:
        if sem_asteriscos.lower().startswith(rotulo):
            resto = sem_asteriscos[len(rotulo):]
            resto = resto.lstrip("*").strip()  # fecha "**Rótulo**" quando o rótulo inteiro é negrito
            resto = _SUFIXO_MIN.sub("", resto)
            resto = resto.lstrip(":").strip().lstrip("*").strip()  # fecha "**Rótulo:**" (":" ainda dentro do negrito)
            return chave, resto
    return None, None


def extrai_disciplinas(texto_md):
    linhas = _secao_anexo_a(texto_md.splitlines())
    disciplinas = []
    atual = None
    for linha in linhas:
        if not linha.startswith("|") or re.match(r"^\|\s*-{2,}", linha):
            continue
        for celula in _celulas(linha):
            chave, valor = _campo(celula)
            if chave is None:
                continue
            if chave == "PERIODO":
                if atual:
                    disciplinas.append(atual)
                atual = {"PERIODO": valor}
            elif atual is not None:
                atual[chave] = valor
    if atual:
        disciplinas.append(atual)

    avisos = []
    for campo in ("DISCIPLINA", "PROFESSOR", "EMENTA", "BIBLIOGRAFIA_BASICA", "BIBLIOGRAFIA_COMPLEMENTAR"):
        faltando = sum(1 for d in disciplinas if not d.get(campo))
        if faltando:
            avisos.append(f"{faltando} de {len(disciplinas)} disciplinas sem '{campo}' (ausente ou vazio) — conferir manualmente")
    sem_justificativa = sum(1 for d in disciplinas if not d.get("JUSTIFICATIVA"))
    if sem_justificativa:
        avisos.append(f"{sem_justificativa} de {len(disciplinas)} disciplinas sem 'Justificativa' — comum no PPC, não é erro de parsing")
    return disciplinas, avisos


def main():
    if len(sys.argv) != 2:
        print("uso: python3 extrai_ppc.py ppc_convertido.md", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        texto = f.read()
    disciplinas, avisos = extrai_disciplinas(texto)
    print(json.dumps({"disciplinas": disciplinas, "avisos": avisos}, ensure_ascii=False, indent=2))


def demo():
    """python3 extrai_ppc.py --demo — cobre os formatos de rótulo reais do
    PPC: `**X**:`, `**X:**`, sem negrito nenhum (`X:`), sufixo `(min. N)`
    na Bibliografia, plural 'Temas de Estudos', campo ausente
    (Justificativa) e campo presente mas vazio (Professor)."""
    md = """# ANEXO A – PLANOS DE ENSINO

|  |
| --- |
| **1º PERÍODO** |

|  |  |  |
| --- | --- | --- |
| **Período**: 1º | **Disciplina**: Fundamentos de Sistemas Ciberfisicos | **Professor**:  Alison Lando |
| **CH (HR):** 60 | **CH (HA):** 80 |  |
| **Ementa**:  Texto da ementa 1. | | |
| **Temas de Estudo**:  TE1; TE2. | | |
| **Bibliografia Básica** (min. 3):  1. Ref básica A. | | |
| **Bibliografia Complementar** (min. 5):  1. Ref complementar A. | | |
| **Justificativa**:  Texto da justificativa 1. | | |
| **Período:** 2º | **Disciplina:**  Banco de Dados | **Professor:**  Cristina Souza |
| **CH (HR):** 60 | **CH (HA):** 80 |  |
| **Ementa**:  Texto da ementa 2. | | |
| **Temas de Estudos**:  TE1; TE2. | | |
| **Bibliografia Básica**:  1. Ref básica B. | | |
| Bibliografia Complementar (min. 5):  1. Ref complementar B. | | |
| JUSTIFICATIVA:  Texto da justificativa 2. | | |
| **Período**: 6º | **Disciplina**: Mobile Development: Framework | **Professor** |
| **CH (HR):** 60 | **CH (HA):** 80 |  |
| **Ementa**:  Texto da ementa 3. | | |
| **Bibliografia Básica**:  1. Ref básica C. | | |
| **Bibliografia Complementar**:  1. Ref complementar C. | | |

# ANEXO B – PROJETO DE CURRICULARIZAÇÃO DA EXTENSÃO

lixo que não deve entrar na extração.
"""
    disciplinas, avisos = extrai_disciplinas(md)
    assert len(disciplinas) == 3, disciplinas

    d1 = disciplinas[0]
    assert d1["DISCIPLINA"] == "Fundamentos de Sistemas Ciberfisicos"
    assert d1["CH_HR"] == "60" and d1["CH_HA"] == "80"
    assert d1["BIBLIOGRAFIA_BASICA"] == "1. Ref básica A.", d1["BIBLIOGRAFIA_BASICA"]
    assert d1["JUSTIFICATIVA"] == "Texto da justificativa 1."

    d2 = disciplinas[1]
    assert d2["PERIODO"] == "2º", "rótulo '**Período:**' (dois-pontos dentro do negrito) não normalizou"
    assert d2["DISCIPLINA"] == "Banco de Dados"
    assert d2["TEMAS_ESTUDO"] == "TE1; TE2.", "rótulo plural 'Temas de Estudos' não mapeou pro mesmo campo"
    assert d2["BIBLIOGRAFIA_COMPLEMENTAR"] == "1. Ref complementar B.", "rótulo sem negrito nenhum não casou"
    assert d2["JUSTIFICATIVA"] == "Texto da justificativa 2.", "'JUSTIFICATIVA:' maiúsculo sem negrito não casou"

    d3 = disciplinas[2]
    assert d3["DISCIPLINA"] == "Mobile Development: Framework", "':' dentro do nome da disciplina não deveria cortar o valor"
    assert d3["PROFESSOR"] == "", "célula '**Professor**' sem valor deveria dar string vazia, não quebrar"
    assert "JUSTIFICATIVA" not in d3, "disciplina sem Justificativa não deveria inventar o campo"

    assert any("Justificativa" in a for a in avisos), avisos
    assert any("PROFESSOR" in a for a in avisos), "Professor vazio devia gerar aviso agregado"
    assert not any("ANEXO B" in d.get("EMENTA", "") or "lixo" in d.get("EMENTA", "") for d in disciplinas)

    print(f"demo ok — {len(disciplinas)} disciplinas extraídas, {len(avisos)} aviso(s) agregado(s)")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
