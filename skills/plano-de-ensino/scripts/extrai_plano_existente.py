#!/usr/bin/env python3
"""Lê um `.docx` real de plano de ensino (template oficial PUCPR "Percursos
Formativos", já preenchido por um professor) e extrai os dados pro mesmo
formato de entrada que `preencher_template.py` consome:
`{"valores": {...}, "linhas_repetir": {...}, "secoes_opcionais": [...], "contexto_disciplinas": {...}}`.

Só biblioteca padrão (`zipfile` + `xml.etree.ElementTree`) — é leitura, não
escrita, então não tem a restrição de "nunca reserializar a árvore inteira"
que vale pro caminho de escrita (`preencher_template.py`/
`limpar_template_oficial.py`); aqui só navegamos a árvore, nunca gravamos
XML de volta.

Uso:
    python3 extrai_plano_existente.py plano_original.docx > extraido.json

Localiza cada seção casando o texto do parágrafo de heading contra os
mesmos textos-âncora usados em `limpar_template_oficial.py`. Um parágrafo
de heading só existe como filho direto de `<w:body>` (nunca dentro de
`<w:tbl>`), então nunca confunde com texto de célula de tabela que contenha
a mesma palavra (ex: cabeçalho de coluna "Competência").

Suporta os layouts reais observados no corpus:
- Mesclas de tabela: resolve `w:vMerge` repetindo o texto da célula que iniciou
  a mescla; `w:gridSpan` N ocupa N colunas lógicas na linha (a 1ª coluna recebe
  o texto da célula e as demais colunas extras recebem string vazia `""` para
  evitar repetição espúria em leituras posicionais como capa ou cronograma).
- Seção 2 (Contexto): além do texto corrido em `valores["CONTEXTO"]`, extrai
  `contexto_disciplinas` = `{"precedentes": [...], "posteriores": [...]}`,
  lido de tabelas reais de 2 colunas (`Código | Disciplina`) e 3 colunas
  (`Código | Período | Nome da disciplina`). Distingue precedentes de
  posteriores pelo rótulo do parágrafo anterior ou cabeçalho.
- Seção 3 (Competências):
  1. Tabela única oficial de 5 colunas (Competência | Elementos de Competência |
     I/M | Temas de Estudo | RA).
  2. Tabela única de 4 colunas (vista em Experiência Criativa e no template
     oficial tokenizado).
  3. Layout "3 tabelas separadas": tabela de Competências + tabela de Resultados
     de Aprendizagem, tanto na Variante A com coluna de classificação (I/M)
     quanto na Variante B sem classificação (campo ausente gera aviso específico).
- Seção 4 (Alinhamento Construtivo): junta tabelas de 4 colunas e aceita também
  tabela de Indicadores de 3 colunas (RA | Nº/ID | Indicador de Desempenho),
  agrupando os indicadores por RA.
- Seção 5 (Cronograma): tabela de 4+ colunas e tabela de 3 colunas (Ano/Mês |
  Dia | Atividades desenvolvidas), mapeada para CRONO_PERIODO (DD/MM).

Global Classes (plano em inglês): os headings e os rótulos da capa também são
reconhecidos em inglês, a partir de `TRADUCAO_EN` (dicionário PT -> EN dos
textos fixos do template, usado também por `limpar_template_oficial.py --en`).
As chaves devolvidas são as mesmas do plano em português. Se a Ementa for
bilíngue (modelo Big Data: texto PT + nota do programa, depois um bloco
"(Syllabus) ..." em inglês), `valores["EMENTA"]` fica com a parte PT e
`valores["EMENTA_EN"]` com o bloco em inglês, sem perder texto.

Nunca decide sozinho quando a extração é ambígua: toda incerteza vira um
item em "avisos", quem resolve é quem está montando o plano.
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

HEADINGS = {
    "ementa": "EMENTA:",
    "contexto": "CONTEXTO DA DISCIPLINA",
    "competencias": "COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM",
    "alinhamento": "ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO",
    "cronograma": "CRONOGRAMA DE ATIVIDADES PEDAGÓGICAS",
    "regras_disciplina": "REGRAS DA DISCIPLINA",
    "bibliografia": "BIBLIOGRAFIA",
    "orientacoes": "ORIENTAÇÕES GERAIS",
}

# Dicionário único PT -> EN dos textos fixos do template (headings, rótulos da
# capa, cabeçalhos de tabela, orientações gerais, rodapé), para as disciplinas
# "Global Classes" (plano escrito em inglês). Mora aqui, junto dos headings PT,
# porque o extrator usa os headings EN pra reconhecer um plano em inglês e
# `limpar_template_oficial.py --en` importa este mesmo dict pra gerar o
# template EN — uma fonte só, sem duplicar. Chave = texto PT do template
# tokenizado, com espaços normalizados (`" ".join(texto.split())`).
#
# Origem dos textos EN:
# - bloco "real": copiado de um plano Global Classes real em inglês (par
#   oficial do corpus do repo de desenvolvimento);
# - bloco "sem par real": o template PT tem esse texto, mas o .docx EN real
#   não — tradução minha, montada com o vocabulário do EN real; revisar com o
#   NDE/Global Classes antes de tratar como texto oficial.
TRADUCAO_EN = {
    # --- real ---
    "Pontifícia Universidade Católica do Paraná": "Pontifical Catholic University of Paraná",
    "PLANO DE ENSINO": "COURSE PLAN",
    "Escola/ Câmpus:": "School/Campus:",
    "Curso:": "Program:",
    "Período:": "Semester:",
    "Turma:": "Section:",
    "Turno:": "Shift:",
    "Carga Horária:": "Workload:",
    "Créditos:": "Credits:",
    "Carga Horária de Extensão:": "Extension Hours:",
    "Requisitos:": "Prerequisites:",
    "EMENTA:": "COURSE DESCRIPTION:",
    "CONTEXTO DA DISCIPLINA": "COURSE CONTEXT",
    "COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM": "COMPETENCIES, STUDY TOPICS, AND LEARNING OUTCOMES",
    "Disciplinas Internalizadoras e Mobilizadoras": "Courses that Internalize and Mobilize Competencies",
    "ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO": "CONSTRUCTIVE ALIGNMENT: METHODOLOGY AND ASSESSMENT",
    "CRONOGRAMA DE ATIVIDADES PEDAGÓGICAS": "COURSE SCHEDULE",
    "RA": "LO",
    "Descrição das atividades pedagógicas": "Description of Learning Activities",
    "BIBLIOGRAFIA": "REFERENCES",
    "Básica:": "Core References:",
    "Complementar:": "Supplementary References:",
    "ORIENTAÇÕES GERAIS": "GENERAL GUIDELINES",
    "Orientações para uso de Inteligência Artificial Generativa (IAGen)": "Guidelines for the Use of Generative Artificial Intelligence (GenAI)",
    "De acordo com a Resolução nº 274/2024 CONSUN, a utilização de ferramentas de Inteligência Artificial Generativa (IAGen) no ensino, aprendizagem e pesquisa da PUCPR deverá ocorrer de acordo com orientações explícitas do docente, que indicará quando, se e de que forma o uso pode acontecer. Ao utilizar qualquer ferramenta de IA, o estudante deve declarar explicitamente o uso, incluindo a seguinte declaração padrão nos materiais produzidos:": "In accordance with CONSUN Resolution No. 274/2024, the use of Generative Artificial Intelligence (GenAI) tools in teaching, learning, and research at PUCPR must follow explicit instructions provided by the instructor, who will indicate when, whether, and how such tools may be used. When using any AI tool, students must explicitly disclose its use by including the following standard statement in the materials produced:",
    "“Durante a preparação deste [TIPO DE CONTEÚDO], o(s) autor(es) usaram [FERRAMENTA, VERSÃO] para [EXPLICITAR MOTIVOS]. Após usar essa ferramenta, o(s) autor(es) revisaram e editaram o conteúdo conforme necessário e assumem total responsabilidade pelo conteúdo.”": "“During the preparation of this [TYPE OF CONTENT], the author(s) used [TOOL, VERSION] for [STATE PURPOSES]. After using this tool, the author(s) reviewed and edited the content as necessary and assume full responsibility for the content.”",
    "Clique aqui para acessar as Diretrizes para uso de IA (Inteligência Artificial) na PUCPR": "Click here to access the PUCPR Guidelines for the Use of AI (Artificial Intelligence)",
    "Link para documentos institucionais sobre avaliações, faltas, tratamento especial, Prêmio Marcelino Champagnat e outros.": "Link to institutional documents regarding assessments, absences, special academic arrangements, the Marcelino Champagnat Award, and other matters.",
    "Clique aqui para acessar estes documentos da PUCPR": "Click here to access these PUCPR documents",
    "Percursos Formativos - Centro de Ensino e Aprendizagem da PUCPR (2026)": "Learning Pathways – PUCPR Center for Teaching and Learning (2026)",
    # --- sem par real ---
    "REGRAS DA DISCIPLINA": "COURSE RULES",
    "Competência e Elementos de Competência": "Competencies and Competency Elements",
    "I/M": "I/M",
    "Temas de Estudo": "Study Topics",
    "Resultados de Aprendizagem": "Learning Outcomes",
    "*(I) – Internalização | (M) – Mobilização.": "*(I) – Internalization | (M) – Mobilization.",
    "Disciplinas Certificadoras": "Courses that Certify Competencies",
    "Resultado de Aprendizagem (Competência)": "Learning Outcome (Competency)",
    "Mapa Mental (opcional - se não utilizar, retirar este item)": "Mind Map (optional - if not used, remove this item)",
    "Resultado(s) de aprendizagem": "Learning Outcome(s)",
    "Indicadores de desempenho": "Performance Indicators",
    "Metodologias, recursos e estratégias de ensino-aprendizagem": "Teaching and learning methodologies, resources, and strategies",
    "Processos de avaliação e recuperação de aprendizagem": "Assessment and reassessment processes",
    "Período": "Period",
    "(dia, semana, quinzena ou mês)": "(day, week, two-week period, or month)",
    "[Trabalho Discente Efetivo (pré ou pós-aula), aulas, práticas, extensão, entre outras.]": "[Independent Learning Activities (before or after class), classes, practical activities, extension, among others.]",
    "Carga horária": "Workload",
    "[HA ou HR]": "[Class Hours or Clock Hours]",
}

ROTULOS_CAPA = {
    "escola/ câmpus": "ESCOLA",
    "escola": "ESCOLA",
    "curso": "CURSO",
    "período": "PERIODO",
    "turma": "TURMA",
    "turno": "TURNO",
    "carga horária de extensão": "CARGA_EXTENSAO",
    "carga horária": "CARGA_HORARIA",
    "créditos": "CREDITOS",
    "requisitos": "REQUISITOS",
}

# Âncoras dos headings em inglês (plano Global Classes), mesmas chaves do PT.
HEADINGS_EN = {chave: TRADUCAO_EN[ancora] for chave, ancora in HEADINGS.items()}

MESES_NUM = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "marco": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


def _texto(elem):
    """Extrai texto de um elemento OpenXML (<w:p>, <w:tc>, etc.).

    - Em células (<w:tc>) ou elementos com múltiplos parágrafos, junta os
      parágrafos (<w:p>) com espaço para evitar colar linhas.
    - Preserva quebras de linha (<w:br>, <w:cr>) como \n (ida e volta).
    - Normaliza espaços/tabs consecutivos em um único espaço.
    """
    if elem.tag == f"{W}tc" or elem.findall(f"{W}p"):
        ps = [_texto_paragrafo(p) for p in elem.findall(f"{W}p")]
        return " ".join(p for p in ps if p).strip()
    return _texto_paragrafo(elem)


def _texto_paragrafo(elem):
    partes = []
    for node in elem.iter():
        if node.tag == f"{W}t":
            partes.append(node.text or "")
        elif node.tag in (f"{W}br", f"{W}cr"):
            partes.append("\n")
    return re.sub(r"[ \t]+", " ", "".join(partes)).strip()


def _linhas_tabela(tbl):
    """<w:tbl> -> lista de linhas, cada linha é lista de textos de célula.

    Resolve mesclas de células OpenXML:
    - `w:vMerge`: célula com continuação vertical repete o texto da célula
      que iniciou a mescla (`w:val="restart"`).
    - `w:gridSpan`: célula que ocupa N colunas preenche N colunas lógicas na
      linha; a primeira coluna recebe o texto da célula e as demais colunas
      adicionais recebem string vazia `""` para evitar duplicar dados em
      chamadores posicionais (ex: identificação, cronograma).
    """
    grid = []
    v_active = {}
    for tr in tbl.findall(f"{W}tr"):
        row = []
        col_idx = 0
        for tc in tr.findall(f"{W}tc"):
            tcPr = tc.find(f"{W}tcPr")
            gs = 1
            if tcPr is not None:
                gs_elem = tcPr.find(f"{W}gridSpan")
                if gs_elem is not None:
                    gs = int(gs_elem.attrib.get(f"{W}val", "1"))

            vm = None
            if tcPr is not None:
                vm_elem = tcPr.find(f"{W}vMerge")
                if vm_elem is not None:
                    vm = vm_elem.attrib.get(f"{W}val", "continue")

            raw_text = _texto(tc)
            if vm == "restart":
                cell_text = raw_text
                for c in range(col_idx, col_idx + gs):
                    v_active[c] = cell_text
            elif vm in ("continue", "continuation") or (vm is not None and vm != "restart"):
                cell_text = v_active.get(col_idx, raw_text)
                for c in range(col_idx, col_idx + gs):
                    v_active[c] = cell_text
            else:
                cell_text = raw_text
                for c in range(col_idx, col_idx + gs):
                    v_active.pop(c, None)

            row.append(cell_text)
            for _ in range(1, gs):
                row.append("")
            col_idx += gs
        grid.append(row)
    return grid


def _normaliza_rotulo(s):
    return " ".join(s.strip().rstrip(":").strip().lower().split())


# Rótulos da capa em inglês (plano Global Classes): mesmos campos do PT,
# derivados do dicionário — "Semester:" vira PERIODO como "Período:".
for _pt, _en in TRADUCAO_EN.items():
    if _normaliza_rotulo(_pt) in ROTULOS_CAPA:
        ROTULOS_CAPA[_normaliza_rotulo(_en)] = ROTULOS_CAPA[_normaliza_rotulo(_pt)]


def carrega_corpo(caminho_docx):
    """.docx -> lista de elementos filhos diretos de <w:body> (w:p, w:tbl,
    w:sectPr...), na ordem do documento."""
    with zipfile.ZipFile(caminho_docx) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(f"{W}body")
    return list(body)


def localiza_headings(corpo):
    """Casa parágrafos de nível de corpo (nunca célula de tabela) contra os
    textos-âncora conhecidos, em português ou em inglês (plano Global
    Classes) — a chave devolvida é a mesma nos dois idiomas. Retorna
    {chave: índice em `corpo`}, na ordem em que aparecem no documento (dict
    preserva ordem de inserção)."""
    achados = {}
    for i, elem in enumerate(corpo):
        if elem.tag != f"{W}p":
            continue
        texto = _texto(elem).rstrip("*").strip().upper()
        for chave, ancora in HEADINGS.items():
            if chave in achados:
                continue
            if texto.startswith(ancora.upper()) or texto.startswith(HEADINGS_EN[chave].upper()):
                achados[chave] = i
                break
    return achados


def _limite(headings, chave, tamanho_corpo):
    """Índice onde a seção `chave` termina: início da próxima heading
    encontrada (não precisa estar em ordem no dict) ou fim do corpo."""
    if chave not in headings:
        return tamanho_corpo
    posteriores = [idx for idx in headings.values() if idx > headings[chave]]
    return min(posteriores) if posteriores else tamanho_corpo


def extrai_identificacao(corpo, headings):
    """Capa: 3 parágrafos não-vazios (Disciplina/Professor/Ano-Semestre)
    logo após o título institucional fixo, + a 1ª tabela do documento
    (Escola/Curso/Período/Turma/Turno/Carga horária/Créditos/Carga de
    extensão/Requisitos, em pares rótulo→valor por linha)."""
    avisos = []
    fim = headings.get("ementa", len(corpo))
    primeira_tabela = next((e for e in corpo[:fim] if e.tag == f"{W}tbl"), None)
    paragrafos = [_texto(e) for e in corpo[:fim] if e.tag == f"{W}p" and _texto(e)]
    candidatos = paragrafos[2:5]
    if primeira_tabela is not None:
        # Só a capa (antes da 1ª tabela): se o nome da disciplina quebrou em
        # vários parágrafos, ele ocupa tudo entre o título e Professor/Ano.
        capa = [
            _texto(e)
            for e in corpo[: corpo.index(primeira_tabela)]
            if e.tag == f"{W}p" and _texto(e)
        ]
        if len(capa) > 5:
            candidatos = [" ".join(capa[2:-2]), capa[-2], capa[-1]]
    valores = {}
    if len(candidatos) == 3:
        valores["DISCIPLINA"], valores["PROFESSOR"], valores["ANO_SEMESTRE"] = candidatos
        # Título pode ter quebra de linha (<w:br>) entre palavras: vira espaço.
        valores["DISCIPLINA"] = " ".join(valores["DISCIPLINA"].split())
    else:
        avisos.append(
            f"identificação: esperava 3 parágrafos (Disciplina/Professor/Ano-Semestre) no topo, achei {len(candidatos)} — preencher manualmente"
        )

    if primeira_tabela is None:
        avisos.append("identificação: tabela da capa (Escola/Curso/...) não encontrada")
        return valores, avisos

    for linha in _linhas_tabela(primeira_tabela):
        for i, c in enumerate(linha):
            campo = ROTULOS_CAPA.get(_normaliza_rotulo(c))
            if campo and campo not in valores:
                for j in range(i + 1, len(linha)):
                    tj = linha[j].strip()
                    if not tj:
                        continue
                    if ROTULOS_CAPA.get(_normaliza_rotulo(tj)):
                        break
                    valores[campo] = tj
                    break
    return valores, avisos


def extrai_paragrafo(corpo, headings, chave):
    """Texto corrido (parágrafos concatenados) entre o heading `chave` e o
    próximo heading conhecido."""
    if chave not in headings:
        return None, [f"seção '{chave}' não encontrada"]
    inicio = headings[chave] + 1
    fim = _limite(headings, chave, len(corpo))
    partes = [_texto(e) for e in corpo[inicio:fim] if e.tag == f"{W}p" and _texto(e)]
    return "\n".join(partes), []


_SYLLABUS = re.compile(r"\(?syllabus\)?(?![\w])", re.IGNORECASE)


def separa_ementa_bilingue(ementa):
    """Ementa bilíngue (modelo Big Data: texto PT + nota do programa Global
    Classes, depois um parágrafo "(Syllabus) ..." em inglês) -> (ementa PT,
    bloco EN, avisos). O bloco EN começa no 1º parágrafo que abre com
    "(Syllabus)"/"Syllabus" e vai até o fim da seção, mantendo o rótulo, pra
    não perder texto: `ementa` + "\n" + `bloco` reconstrói o original. Sem
    rótulo, devolve (ementa, None, []). Rótulo no meio de um parágrafo não é
    separado (não dá pra saber onde o inglês começa): vira aviso."""
    paragrafos = ementa.split("\n")
    for i, paragrafo in enumerate(paragrafos):
        if _SYLLABUS.match(paragrafo):
            return "\n".join(paragrafos[:i]), "\n".join(paragrafos[i:]), []
    if "(syllabus)" in ementa.lower():
        return ementa, None, [
            "seção 'Ementa': '(Syllabus)' no meio de um parágrafo — não separei o bloco em inglês, conferir manualmente"
        ]
    return ementa, None, []


def extrai_contexto(corpo, headings):
    """Extrai o texto corrido da seção 'Contexto da Disciplina' e tabelas de
    disciplinas precedentes e posteriores.

    Retorna (texto, contexto_disciplinas, avisos).
    `contexto_disciplinas` é um dicionário:
        {"precedentes": [...], "posteriores": [...]}
    onde cada item é:
        {"codigo": str, "periodo": str | None, "nome": str}

    Baseado nas variantes reais do corpus:
    - 2 colunas: Código | Disciplina (ex: PJD117A - Data Analytics.docx)
    - 3 colunas: Código | Período | Nome da disciplina (ex: Plano de Ensino - Engenharia de Software.docx)

    Classifica como precedentes ou posteriores examinando o parágrafo anterior
    e o cabeçalho da tabela; se for ambíguo, gera aviso em vez de adivinhar.
    """
    contexto, av = extrai_paragrafo(corpo, headings, "contexto")
    avisos = list(av)
    contexto_disciplinas = {"precedentes": [], "posteriores": []}
    if "contexto" not in headings:
        return contexto, contexto_disciplinas, avisos

    inicio = headings["contexto"] + 1
    fim = _limite(headings, "contexto", len(corpo))
    precedentes = []
    posteriores = []
    last_p = ""
    for idx in range(inicio, fim):
        elem = corpo[idx]
        if elem.tag == f"{W}p":
            t = _texto(elem)
            if t:
                last_p = t
        elif elem.tag == f"{W}tbl":
            grid = _linhas_tabela(elem)
            if not grid:
                continue
            hdr = [c.lower() for c in grid[0]]
            is_2col = (
                len(hdr) == 2
                and any("código" in c or "codigo" in c for c in hdr)
                and any("disciplina" in c or "nome" in c for c in hdr)
            )
            is_3col = (
                len(hdr) == 3
                and any("código" in c or "codigo" in c for c in hdr)
                and any("disciplina" in c or "nome" in c for c in hdr)
                and any("período" in c or "periodo" in c for c in hdr)
            )
            if not (is_2col or is_3col):
                continue

            p_lower = last_p.lower()
            h_lower = " ".join(hdr)
            if "precedente" in p_lower or "precedente" in h_lower:
                dest = precedentes
            elif (
                "posterior" in p_lower
                or "contribui" in p_lower
                or "fornece a base" in p_lower
                or "posterior" in h_lower
            ):
                dest = posteriores
            else:
                dest = None
                avisos.append(
                    "seção 'Contexto': não foi possível determinar se a tabela de disciplinas é de precedentes ou posteriores — conferir manualmente"
                )

            if dest is not None:
                for r in grid[1:]:
                    if is_2col:
                        c0, c1 = r[0].strip(), r[1].strip()
                        if c0 or c1:
                            dest.append({"codigo": c0, "periodo": None, "nome": c1})
                    elif is_3col:
                        c0, c1, c2 = r[0].strip(), r[1].strip(), r[2].strip()
                        if c0 or c1 or c2:
                            dest.append({"codigo": c0, "periodo": c1 or None, "nome": c2})

    contexto_disciplinas["precedentes"] = precedentes
    contexto_disciplinas["posteriores"] = posteriores
    return contexto, contexto_disciplinas, avisos


def _extrai_competencias_tabela_unica_5col(linhas):
    """Extrai IM_RA da tabela única oficial de 5 colunas:
    Competência | Elementos de Competência | I/M | Temas de Estudo | RA.
    Baseado em: Plano de Ensino - Resolução de Problemas Estruturados em Computação.docx,
    Desenvolvimento de Carreira, Jogos com Unreal, Raciocínio Algorítmico (Turma A).
    """
    im_ra = []
    avisos = []
    competencia_atual = ""
    for linha in linhas[1:]:
        if len(linha) != 5:
            avisos.append(
                f"seção 'Competências': linha com {len(linha)} célula(s) em vez de 5 (célula mesclada em formato inesperado) — pulada, conferir manualmente"
            )
            continue
        comp, ec, im, temas, ra = (c.strip() for c in linha)
        if not (comp or ec or im or temas or ra):
            continue
        if comp:
            competencia_atual = comp
        im_ra.append({
            "IM_COMPETENCIA": f"{competencia_atual}\n{ec}".strip("\n") if ec else competencia_atual,
            "IM_CLASSIFICACAO": im,
            "IM_TEMAS": temas,
            "IM_RA": ra,
        })
    if any(not item["IM_RA"] for item in im_ra):
        avisos.append(
            "seção 'Competências': alguma linha ficou sem RA — conferir junção de células mescladas"
        )
    return im_ra, avisos


def _extrai_competencias_tabela_unica_4col(linhas):
    """Extrai IM_RA da tabela única de 4 colunas:
    Competência e Elementos de Competência | I/M | Temas de Estudo | Resultados de Aprendizagem.
    Baseado em: Plano de Ensino - Experiência Criativa - Projetando Sistemas de Informação.docx
    e assets/template-oficial-tokenizado.docx.
    Detecta se col 0 e col 3 estão invertidas (quando col 0 traz o código de RA).
    """
    im_ra = []
    avisos = []
    competencia_atual = ""

    inverte_cols = False
    for linha in linhas[1:]:
        if len(linha) >= 4:
            c0, c3 = linha[0].strip(), linha[3].strip()
            if c0.upper().startswith("RA") and not c3.upper().startswith("RA"):
                inverte_cols = True
                break

    for linha in linhas[1:]:
        if len(linha) < 4:
            continue
        if inverte_cols:
            ra, im, temas, comp = (c.strip() for c in linha[:4])
        else:
            comp, im, temas, ra = (c.strip() for c in linha[:4])

        if not (comp or im or temas or ra):
            continue
        if comp:
            competencia_atual = comp
        im_ra.append({
            "IM_COMPETENCIA": competencia_atual,
            "IM_CLASSIFICACAO": im,
            "IM_TEMAS": temas,
            "IM_RA": ra,
        })
    if any(not item["IM_RA"] for item in im_ra):
        avisos.append("seção 'Competências': alguma linha ficou sem RA — conferir manualmente")
    return im_ra, avisos


def _extrai_competencias_3tabelas(tabelas):
    """Extrai IM_RA do layout '3 tabelas separadas' (Competências + RAs):
    Baseado em:
    - PJD117A - Data Analytics.docx, PJD117A - Inteligência Artificial.docx,
      Plano de Ensino - Raciocínio Algorítmico (Turma U).docx (Variante A: com classificação I/M)
    - Plano de Ensino - Engenharia de Software.docx, AI-Assisted Python, Especificação,
      Gestão de Projetos, Métodos e Ferramentas (Variante B: sem coluna de classificação I/M)
    """
    tbl_comp = None
    tbl_ra = None
    for t in tabelas:
        grid = _linhas_tabela(t)
        if not grid:
            continue
        hdr = " ".join(grid[0]).lower()
        if ("competência" in hdr or "competency" in hdr) and not tbl_comp:
            tbl_comp = grid
        elif (("resultado" in hdr and ("aprendizagem" in hdr or "ra" in hdr)) or "learning outcome" in hdr) and not tbl_ra:
            tbl_ra = grid

    if not (tbl_comp and tbl_ra):
        return [], [
            "seção 'Competências': tabelas de Competências e Resultados de Aprendizagem não encontradas no layout '3 tabelas separadas' — preencher IM_RA manualmente"
        ]

    ec_map = {}
    competencia_atual = ""
    tem_classificacao = False
    for r in tbl_comp[1:]:
        if len(r) >= 4:
            comp = r[1].strip()
            nec = r[2].strip()
            ec_desc = r[3].strip()
            im = r[4].strip() if len(r) >= 5 else ""
            if len(r) >= 5 and r[4].strip():
                tem_classificacao = True
            if comp:
                competencia_atual = comp
            if nec:
                norm_nec = re.sub(r"\s+", "", nec).upper()
                ec_map[norm_nec] = {"comp": competencia_atual, "ec": ec_desc, "im": im, "nec": nec}

    avisos = []
    if not tem_classificacao:
        avisos.append(
            "seção 'Competências': layout '3 tabelas separadas' sem coluna de classificação (I/M) — preencher manualmente"
        )

    im_ra = []
    ec_atual = ""
    for r in tbl_ra[1:]:
        if len(r) < 4:
            continue
        ec_col, ra_num, ra_desc, temas = (c.strip() for c in r[:4])
        if not (ec_col or ra_num or ra_desc or temas):
            continue
        if ec_col:
            ec_atual = ec_col
        ra_code = ra_num if ra_num else ra_desc

        found_ecs = re.findall(r"(?:EC|CE)\s*[A-Za-z0-9.]+", ec_atual, re.IGNORECASE)
        comps = []
        ecs = []
        ims = []
        for fec in found_ecs:
            norm = re.sub(r"\s+", "", fec).upper()
            if norm in ec_map:
                info = ec_map[norm]
                if info["comp"] and info["comp"] not in comps:
                    comps.append(info["comp"])
                if info["ec"]:
                    nec_label = info["nec"]
                    ec_text = info["ec"]
                    ecs.append(f"{nec_label} – {ec_text}" if nec_label else ec_text)
                if info["im"] and info["im"] not in ims:
                    ims.append(info["im"])

        comp_str = "\n".join(comps) if comps else competencia_atual
        ec_str = "\n".join(ecs)
        im_comp = f"{comp_str}\n{ec_str}".strip("\n") if ec_str else comp_str
        im_classif = "/".join(ims) if ims else ""

        im_ra.append({
            "IM_COMPETENCIA": im_comp,
            "IM_CLASSIFICACAO": im_classif,
            "IM_TEMAS": temas,
            "IM_RA": ra_code,
        })

    if any(not item["IM_RA"] for item in im_ra):
        avisos.append("seção 'Competências': alguma linha ficou sem RA — conferir manualmente")
    return im_ra, avisos


def extrai_competencias(corpo, headings):
    """Linhas `IM_RA`:
    Suporta três estilos reais observados no corpus:
    1. Tabela única de 5 colunas (oficial):
       Competência | Elementos de Competência | I/M | Temas de Estudo | Resultados de Aprendizagem
       (ex: Plano de Ensino - Resolução de Problemas Estruturados em Computação.docx)
    2. Tabela única de 4 colunas:
       Competência e Elementos de Competência | I/M | Temas de Estudo | Resultados de Aprendizagem
       (ex: Plano de Ensino - Experiência Criativa - Projetando Sistemas de Informação.docx
        e template-oficial-tokenizado.docx)
    3. Layout '3 tabelas separadas':
       Tabela de Competências + Tabela de Resultados de Aprendizagem
       - Variante A com classificação I/M (ex: PJD117A - Data Analytics.docx,
         PJD117A - Inteligência Artificial.docx, Plano de Ensino - Raciocínio Algorítmico (Turma U).docx)
       - Variante B sem coluna de classificação I/M (ex: Plano de Ensino - Engenharia de Software.docx,
         Especificação, Gestão de Projetos, Métodos e Ferramentas, AI-Assisted Python)
    """
    if "competencias" not in headings:
        return [], ["seção 'Competências' não encontrada"]
    inicio = headings["competencias"] + 1
    fim = _limite(headings, "competencias", len(corpo))
    tabelas = [e for e in corpo[inicio:fim] if e.tag == f"{W}tbl"]
    if not tabelas:
        return [], ["seção 'Competências': tabela não encontrada"]

    if len(tabelas) == 1:
        linhas = _linhas_tabela(tabelas[0])
        if not linhas:
            return [], ["seção 'Competências': tabela vazia"]
        n_cols = len(linhas[0])
        if n_cols == 5:
            return _extrai_competencias_tabela_unica_5col(linhas)
        elif n_cols == 4:
            return _extrai_competencias_tabela_unica_4col(linhas)
        else:
            return [], [
                f"seção 'Competências': esperava tabela de 4 ou 5 colunas, achei {n_cols} — preencher IM_RA manualmente"
            ]

    return _extrai_competencias_3tabelas(tabelas)


def extrai_alinhamento(corpo, headings):
    """Linhas `MET_RA`: tabela(s) de 4 colunas (RA | Indicadores de
    desempenho | Metodologia | Avaliação), uma tabela por RA no template
    oficial — junta todas as encontradas na seção.
    Também aceita tabela de Indicadores de 3 colunas (RA | Nº/ID |
    Indicador de Desempenho), vista em planos como Raciocínio Algorítmico
    (Turma U); agrupa os indicadores por RA e emite aviso de campos ausentes."""
    if "alinhamento" not in headings:
        return [], ["seção 'Alinhamento Construtivo' não encontrada"]
    inicio = headings["alinhamento"] + 1
    fim = _limite(headings, "alinhamento", len(corpo))
    met_ra = []

    # 1. Busca tabelas de 4 colunas (formato oficial)
    for tabela in (e for e in corpo[inicio:fim] if e.tag == f"{W}tbl"):
        linhas = _linhas_tabela(tabela)
        if not linhas or len(linhas[0]) != 4:
            continue
        for linha in linhas[1:]:
            if len(linha) != 4:
                continue
            ra, ind, met, aval = (c.strip() for c in linha)
            if ra or ind or met or aval:
                met_ra.append({
                    "MET_RA": ra,
                    "MET_ID": ind,
                    "MET_METODOLOGIA": met,
                    "MET_AVALIACAO": aval,
                })

    # 2. Se nenhuma tabela de 4 colunas existir, busca tabela de Indicadores de 3 colunas
    avisos = []
    if not met_ra:
        for tabela in (e for e in corpo[inicio:fim] if e.tag == f"{W}tbl"):
            linhas = _linhas_tabela(tabela)
            if not linhas or len(linhas[0]) != 3:
                continue
            hdr = " ".join(linhas[0]).lower()
            if "indicador" in hdr:
                ra_atual = ""
                ras_ordem = []
                indicadores_por_ra = {}
                for linha in linhas[1:]:
                    if len(linha) < 3:
                        continue
                    ra_col, id_col, desc_col = (c.strip() for c in linha[:3])
                    if not (ra_col or id_col or desc_col):
                        continue
                    if ra_col:
                        ra_atual = ra_col
                    if not ra_atual:
                        continue
                    if ra_atual not in indicadores_por_ra:
                        indicadores_por_ra[ra_atual] = []
                        ras_ordem.append(ra_atual)
                    id_completo = f"{id_col} – {desc_col}".strip(" –") if id_col else desc_col
                    if id_completo:
                        indicadores_por_ra[ra_atual].append(id_completo)

                for ra in ras_ordem:
                    met_ra.append({
                        "MET_RA": ra,
                        "MET_ID": "\n".join(indicadores_por_ra[ra]),
                        "MET_METODOLOGIA": "",
                        "MET_AVALIACAO": "",
                    })
                if met_ra:
                    avisos.append(
                        "seção 'Alinhamento Construtivo': extraído da tabela de Indicadores de 3 colunas (metodologia e avaliação ausentes — preencher manualmente)"
                    )
                    break

    if not met_ra and not avisos:
        avisos.append("seção 'Alinhamento Construtivo': nenhuma tabela de 4 colunas encontrada")
    return met_ra, avisos


def extrai_cronograma(corpo, headings):
    """Linhas `CRONO_PERIODO`:
    - Tabela de 4 ou mais colunas (oficial): as 4 últimas colunas são sempre
      Período/Data | RA | Descrição | Carga horária.
    - Tabela de 3 colunas (vista em Experiência Criativa - Projetando Sistemas
      de Informação.docx): Ano/Mês | Dia | Atividades desenvolvidas; mapeia
      para Período (DD/MM) e Descrição, deixando RA e Carga horária vazios."""
    if "cronograma" not in headings:
        return [], ["seção 'Cronograma' não encontrada"]
    inicio = headings["cronograma"] + 1
    fim = _limite(headings, "cronograma", len(corpo))
    tabela = next((e for e in corpo[inicio:fim] if e.tag == f"{W}tbl"), None)
    if tabela is None:
        return [], ["seção 'Cronograma': tabela não encontrada"]

    linhas = _linhas_tabela(tabela)
    if not linhas:
        return [], ["seção 'Cronograma': nenhuma linha extraída"]

    crono = []
    avisos = []
    if len(linhas[0]) >= 4:
        for linha in linhas[1:]:
            if len(linha) < 4:
                continue
            periodo, ra, descricao, carga = (c.strip() for c in linha[-4:])
            if not (periodo or ra or descricao or carga):
                continue
            crono.append({
                "CRONO_PERIODO": periodo,
                "CRONO_RA": ra,
                "CRONO_DESC": descricao,
                "CRONO_CH": carga,
            })
    elif len(linhas[0]) == 3:
        # Variação real: Experiência Criativa - Projetando Sistemas de Informação.docx
        # Colunas: [Ano/Mês, Dia, Atividades desenvolvidas]
        mes_atual = ""
        for linha in linhas[1:]:
            if len(linha) < 3:
                continue
            col_mes, dia, desc = (c.strip() for c in linha[:3])
            if not (col_mes or dia or desc):
                continue
            if col_mes:
                mes_atual = col_mes

            mes_num = MESES_NUM.get(mes_atual.lower(), "")
            if dia and mes_num:
                periodo = f"{dia}/{mes_num}"
            elif dia and mes_atual:
                periodo = f"{dia} ({mes_atual})"
            elif dia:
                periodo = dia
            else:
                periodo = mes_atual

            crono.append({
                "CRONO_PERIODO": periodo,
                "CRONO_RA": "",
                "CRONO_DESC": desc,
                "CRONO_CH": "",
            })
        if crono:
            avisos.append(
                "seção 'Cronograma': tabela de 3 colunas (sem RA e Carga Horária — preencher manualmente)"
            )

    return crono, (avisos if crono else ["seção 'Cronograma': nenhuma linha extraída"])


_PREFIXO_NUMERACAO = re.compile(r"^\d+(\.\d+)*\.?\s*")


def _blocos_biblio(corpo, inicio, fim):
    """Acha os parágrafos-marcador 'Básica:'/'Complementar:' dentro de
    [inicio, fim). Tolera prefixo numerado ("6.1. Básica") tirando os
    dígitos/pontos do início antes de comparar — exige que o texto
    COMECE com a palavra (não usa "in"), senão uma referência real que
    cite "básica" de passagem (ex: um livro sobre "Programação Básica")
    seria confundida com o marcador. Fica com a primeira ocorrência —
    o marcador sempre vem antes das referências, nunca depois."""
    marcador_basica = marcador_compl = None
    for i in range(inicio, fim):
        elem = corpo[i]
        if elem.tag != f"{W}p":
            continue
        t = _PREFIXO_NUMERACAO.sub("", _texto(elem).strip().lower()).strip()
        if marcador_basica is None and t.startswith(("básica", "core")):
            marcador_basica = i
        elif marcador_compl is None and t.startswith(("complementar", "supplementary")):
            marcador_compl = i
    return marcador_basica, marcador_compl


def _extrai_bloco_biblio(corpo, inicio, fim):
    """[inicio, fim) -> lista de referências (str). Tabela `Nº | Referência`
    (usa a última coluna) ou parágrafos soltos (bullets/lista numerada)."""
    tabela = next((e for e in corpo[inicio:fim] if e.tag == f"{W}tbl"), None)
    if tabela is not None:
        return [linha[-1].strip() for linha in _linhas_tabela(tabela)[1:] if linha and linha[-1].strip()]
    return [_texto(e) for e in corpo[inicio:fim] if e.tag == f"{W}p" and _texto(e)]


def extrai_bibliografia(corpo, headings):
    if "bibliografia" not in headings:
        return [], [], ["seção 'Bibliografia' não encontrada"]
    inicio = headings["bibliografia"] + 1
    fim = _limite(headings, "bibliografia", len(corpo))
    marcador_basica, marcador_compl = _blocos_biblio(corpo, inicio, fim)
    if marcador_basica is None or marcador_compl is None:
        return [], [], ["seção 'Bibliografia': marcador 'Básica:'/'Complementar:' não encontrado — preencher manualmente"]
    basica = _extrai_bloco_biblio(corpo, marcador_basica + 1, marcador_compl)
    complementar = _extrai_bloco_biblio(corpo, marcador_compl + 1, fim)
    return basica, complementar, []


def _e_template_2025(corpo, headings):
    """Plano do template antigo: seções numeradas ("1. Ementa:", "4. Resultados de
    Aprendizagem") e nenhum heading do template 2026 reconhecido."""
    if set(headings) - {"bibliografia"}:
        return False
    return any(e.tag == f"{W}p" and _texto(e).strip().lower().startswith("1. ementa") for e in corpo)


def extrai_plano(caminho_docx):
    corpo = carrega_corpo(caminho_docx)
    headings = localiza_headings(corpo)
    avisos = []

    if _e_template_2025(corpo, headings):
        texto = [t for t in (_texto(e).strip() for e in corpo if e.tag == f"{W}p") if t]
        aviso = (
            "plano no template 2025 (seções numeradas, sem os headings do template 2026): nada foi extraído "
            "automaticamente — use `texto_original` como base, refaça a entrevista pré-preenchendo o que "
            "existir e confirme cada seção com o professor; nenhum texto deve ser descartado em silêncio"
        )
        return {"valores": {}, "linhas_repetir": {}, "secoes_opcionais": [],
                "contexto_disciplinas": {}, "texto_original": texto}, [aviso]

    valores, av = extrai_identificacao(corpo, headings)
    avisos += av

    ementa, av = extrai_paragrafo(corpo, headings, "ementa")
    avisos += av
    if ementa is not None:
        ementa, ementa_en, av = separa_ementa_bilingue(ementa)
        avisos += av
        valores["EMENTA"] = ementa
        if ementa_en is not None:
            valores["EMENTA_EN"] = ementa_en

    contexto, contexto_disc, av = extrai_contexto(corpo, headings)
    avisos += av
    if contexto is not None:
        valores["CONTEXTO"] = contexto

    im_ra, av = extrai_competencias(corpo, headings)
    avisos += av
    met_ra, av = extrai_alinhamento(corpo, headings)
    avisos += av
    crono, av = extrai_cronograma(corpo, headings)
    avisos += av
    basica, complementar, av = extrai_bibliografia(corpo, headings)
    avisos += av

    linhas_repetir = {}
    if im_ra:
        linhas_repetir["IM_RA"] = im_ra
    if met_ra:
        linhas_repetir["MET_RA"] = met_ra
    if crono:
        linhas_repetir["CRONO_PERIODO"] = crono
    if basica:
        linhas_repetir["BIBLIOGRAFIA_BASICA"] = [{"BIBLIOGRAFIA_BASICA": r} for r in basica]
    if complementar:
        linhas_repetir["BIBLIOGRAFIA_COMPLEMENTAR"] = [{"BIBLIOGRAFIA_COMPLEMENTAR": r} for r in complementar]

    secoes_opcionais = []
    if "regras_disciplina" in headings:
        corpo_regras, av = extrai_paragrafo(corpo, headings, "regras_disciplina")
        avisos += av
        if corpo_regras:
            heading_en = HEADINGS_EN["regras_disciplina"]
            em_ingles = _texto(corpo[headings["regras_disciplina"]]).upper().startswith(heading_en.upper())
            titulo = heading_en if em_ingles else HEADINGS["regras_disciplina"]
            secoes_opcionais.append({"titulo": titulo, "corpo": corpo_regras})

    dados = {
        "valores": valores,
        "linhas_repetir": linhas_repetir,
        "secoes_opcionais": secoes_opcionais,
        "contexto_disciplinas": contexto_disc,
    }
    return dados, avisos


def main():
    if len(sys.argv) != 2:
        print("uso: python3 extrai_plano_existente.py plano_original.docx", file=sys.stderr)
        sys.exit(1)
    dados, avisos = extrai_plano(sys.argv[1])
    print(json.dumps({"dados": dados, "avisos": avisos}, ensure_ascii=False, indent=2))


def demo():
    """python3 extrai_plano_existente.py --demo"""
    # Caso 1: Tabela oficial de 5 colunas com vMerge e gridSpan
    xml_corpo = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>Pontifícia Universidade Católica do Paraná</w:t></w:r></w:p>
<w:p><w:r><w:t>PLANO DE ENSINO</w:t></w:r></w:p>
<w:p><w:r><w:t>Disciplina Teste</w:t></w:r></w:p>
<w:p><w:r><w:t>Professor Teste</w:t></w:r></w:p>
<w:p><w:r><w:t>2026 – 2º Semestre</w:t></w:r></w:p>
<w:tbl>
<w:tr>
<w:tc><w:p><w:r><w:t>Escola/ Câmpus:</w:t></w:r></w:p></w:tc>
<w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>Politécnica</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>Curso:</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>BSI</w:t></w:r></w:p></w:tc>
</w:tr>
</w:tbl>
<w:p><w:r><w:t>EMENTA:</w:t></w:r></w:p>
<w:p><w:r><w:t>Texto da ementa de teste.</w:t></w:r></w:p>
<w:p><w:r><w:t>CONTEXTO DA DISCIPLINA</w:t></w:r></w:p>
<w:p><w:r><w:t>Disciplinas precedentes:</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Código</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Disciplina</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>DISC01</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Algoritmos</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>Contribui com as disciplinas posteriores:</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Código</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Período</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Nome da disciplina</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>DISC02</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>2º</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Estruturas de Dados</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Competência</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Elementos de Competência</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>I/M</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Temas de Estudo</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Resultados de Aprendizagem</w:t></w:r></w:p></w:tc></w:tr>
<w:tr>
<w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>Competência A</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>EC1</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>I</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>TE1</w:t></w:r></w:p></w:tc>
<w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>RA1</w:t></w:r></w:p></w:tc>
</w:tr>
<w:tr>
<w:tc><w:tcPr><w:vMerge w:val="continue"/></w:tcPr><w:p/></w:tc>
<w:tc><w:p><w:r><w:t>EC2</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>M</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>TE2</w:t></w:r></w:p></w:tc>
<w:tc><w:tcPr><w:vMerge w:val="continue"/></w:tcPr><w:p/></w:tc>
</w:tr>
</w:tbl>
<w:p><w:r><w:t>ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>RA</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Indicadores</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Metodologia</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Avaliação</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>ID1.1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Aula expositiva</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>[Somativa] Prova.</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>CRONOGRAMA DE ATIVIDADES PEDAGÓGICAS*</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Data</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>RA</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Descrição</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Carga horária</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>04/08</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Aula 1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>04:00</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>REGRAS DA DISCIPLINA</w:t></w:r></w:p>
<w:p><w:r><w:t>Texto das regras.</w:t></w:r></w:p>
<w:p><w:r><w:t>BIBLIOGRAFIA</w:t></w:r></w:p>
<w:p><w:r><w:t>Básica:</w:t></w:r></w:p>
<w:p><w:r><w:t>Ref básica 1</w:t></w:r></w:p>
<w:p><w:r><w:t>Ref básica 2</w:t></w:r></w:p>
<w:p><w:r><w:t>Complementar:</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Nº</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Referência</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Ref complementar 1</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>ORIENTAÇÕES GERAIS</w:t></w:r></w:p>
</w:body>"""
    corpo = list(ET.fromstring(xml_corpo))
    headings = localiza_headings(corpo)
    assert set(headings) == set(HEADINGS), f"nem todos os headings foram achados: {sorted(headings)}"

    valores, av = extrai_identificacao(corpo, headings)
    assert valores["DISCIPLINA"] == "Disciplina Teste"
    assert valores["PROFESSOR"] == "Professor Teste"
    assert valores["ANO_SEMESTRE"] == "2026 – 2º Semestre"
    assert valores["ESCOLA"] == "Politécnica" and valores["CURSO"] == "BSI"
    assert av == [], av

    # Seção 2: contexto corrido e disciplinas precedentes/posteriores
    ctx_txt, ctx_disc, av = extrai_contexto(corpo, headings)
    assert "Disciplinas precedentes" in ctx_txt
    assert ctx_disc["precedentes"] == [{"codigo": "DISC01", "periodo": None, "nome": "Algoritmos"}]
    assert ctx_disc["posteriores"] == [{"codigo": "DISC02", "periodo": "2º", "nome": "Estruturas de Dados"}]
    assert av == [], av

    # Seção 3: tabela única de 5 colunas com vMerge de continuação
    im_ra, av = extrai_competencias(corpo, headings)
    assert len(im_ra) == 2, im_ra
    assert im_ra[0]["IM_COMPETENCIA"] == "Competência A\nEC1"
    assert im_ra[1]["IM_COMPETENCIA"] == "Competência A\nEC2"
    assert im_ra[0]["IM_RA"] == "RA1"
    assert im_ra[1]["IM_RA"] == "RA1", "vMerge de continuação de RA não repetiu valor"
    assert av == [], av

    # Caso 2: Seção 3 — tabela única de 4 colunas (Experiência Criativa / template oficial)
    xml_4col = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Competência e Elementos de Competência</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>I/M</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Temas de Estudo</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Resultados de Aprendizagem</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>RA1: Propor soluções</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>I/M</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>TE1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Competência Projetar</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO</w:t></w:r></w:p>
</w:body>"""
    corpo_4col = list(ET.fromstring(xml_4col))
    h_4col = localiza_headings(corpo_4col)
    im_ra_4col, av_4col = extrai_competencias(corpo_4col, h_4col)
    assert len(im_ra_4col) == 1
    assert im_ra_4col[0]["IM_RA"] == "RA1: Propor soluções"
    assert im_ra_4col[0]["IM_COMPETENCIA"] == "Competência Projetar"
    assert im_ra_4col[0]["IM_CLASSIFICACAO"] == "I/M"

    # Caso 3: Seção 3 — layout "3 tabelas separadas" (Variante A com classificação)
    xml_3tab_a = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Nº</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Descrição do tema</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>TE1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Introdução</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Nº C</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Competência</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Nº EC</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Elementos de Competência</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>-</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Comp 1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>EC1.1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Elem 1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Mobiliza</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>EC</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Nº</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Resultado de aprendizagem (RA)</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Tema de estudo</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>EC1.1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Desc RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>TE1</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO</w:t></w:r></w:p>
</w:body>"""
    corpo_3a = list(ET.fromstring(xml_3tab_a))
    h_3a = localiza_headings(corpo_3a)
    im_ra_3a, av_3a = extrai_competencias(corpo_3a, h_3a)
    assert len(im_ra_3a) == 1
    assert im_ra_3a[0]["IM_RA"] == "RA1"
    assert im_ra_3a[0]["IM_CLASSIFICACAO"] == "Mobiliza"
    assert "Comp 1" in im_ra_3a[0]["IM_COMPETENCIA"]
    assert av_3a == [], av_3a

    # Caso 4: Seção 3 — layout "3 tabelas separadas" (Variante B sem coluna de classificação)
    xml_3tab_b = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>Competência</w:t></w:r></w:p></w:tc><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>Elementos de Competência (EC)</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Comp A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>EC A1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Elem A1</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>EC</w:t></w:r></w:p></w:tc><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>Resultado de aprendizagem (RA)</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Tema de estudo (TE)</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>EC A1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Desc RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>TE1</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO</w:t></w:r></w:p>
</w:body>"""
    corpo_3b = list(ET.fromstring(xml_3tab_b))
    h_3b = localiza_headings(corpo_3b)
    im_ra_3b, av_3b = extrai_competencias(corpo_3b, h_3b)
    assert len(im_ra_3b) == 1
    assert im_ra_3b[0]["IM_RA"] == "RA1"
    assert im_ra_3b[0]["IM_CLASSIFICACAO"] == ""
    assert any("sem coluna de classificação" in a for a in av_3b)

    # Caso 5: Seção 4 — tabela de Indicadores de 3 colunas (RA | ID | Indicador)
    xml_ind_3col = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>RA</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Nº</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Indicador de Desempenho</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>RA1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>ID1.1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Ind 1.1</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p/></w:tc><w:tc><w:p><w:r><w:t>ID1.2</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Ind 1.2</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>CRONOGRAMA DE ATIVIDADES PEDAGÓGICAS</w:t></w:r></w:p>
</w:body>"""
    corpo_ind = list(ET.fromstring(xml_ind_3col))
    h_ind = localiza_headings(corpo_ind)
    met_ra_ind, av_ind = extrai_alinhamento(corpo_ind, h_ind)
    assert len(met_ra_ind) == 1
    assert met_ra_ind[0]["MET_RA"] == "RA1"
    assert "ID1.1" in met_ra_ind[0]["MET_ID"] and "ID1.2" in met_ra_ind[0]["MET_ID"]
    assert any("tabela de Indicadores de 3 colunas" in a for a in av_ind)

    # Caso 6: Cronograma de 3 colunas (Ano/Mês | Dia | Atividades)
    xml_crono_3col = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>CRONOGRAMA DE ATIVIDADES PEDAGÓGICAS</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>2026</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Dia</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Atividades desenvolvidas</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>Março</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>03</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Aula 1</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p/></w:tc><w:tc><w:p><w:r><w:t>10</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Aula 2</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>BIBLIOGRAFIA</w:t></w:r></w:p>
</w:body>"""
    corpo_cr3 = list(ET.fromstring(xml_crono_3col))
    h_cr3 = localiza_headings(corpo_cr3)
    crono_3, av_cr3 = extrai_cronograma(corpo_cr3, h_cr3)
    assert len(crono_3) == 2
    assert crono_3[0]["CRONO_PERIODO"] == "03/03" and crono_3[0]["CRONO_DESC"] == "Aula 1"
    assert crono_3[1]["CRONO_PERIODO"] == "10/03" and crono_3[1]["CRONO_DESC"] == "Aula 2"
    assert any("tabela de 3 colunas" in a for a in av_cr3)

    # Caso 7: Ementa bilíngue (modelo Big Data) e headings em inglês
    xml_ementa = """<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:r><w:t>COURSE DESCRIPTION:</w:t></w:r></w:p>
<w:p><w:r><w:t>Disciplina de teste. Importante: esta disciplina é ofertada no nível I do programa Global Classes.</w:t></w:r></w:p>
<w:p><w:r><w:t>(Syllabus) Test course. Offered at level I of the Global Classes program.</w:t></w:r></w:p>
<w:p><w:r><w:t>Second English paragraph.</w:t></w:r></w:p>
<w:p><w:r><w:t>COURSE CONTEXT</w:t></w:r></w:p>
</w:body>"""
    corpo_ementa = list(ET.fromstring(xml_ementa))
    h_ementa = localiza_headings(corpo_ementa)
    assert set(h_ementa) == {"ementa", "contexto"}, "headings EN não reconhecidos"
    texto_ementa, av = extrai_paragrafo(corpo_ementa, h_ementa, "ementa")
    pt, en, av = separa_ementa_bilingue(texto_ementa)
    assert pt == "Disciplina de teste. Importante: esta disciplina é ofertada no nível I do programa Global Classes."
    assert en == "(Syllabus) Test course. Offered at level I of the Global Classes program.\nSecond English paragraph."
    assert pt + "\n" + en == texto_ementa, "separação perdeu texto"
    assert av == [], av
    assert separa_ementa_bilingue("Só texto PT.") == ("Só texto PT.", None, [])
    pt, en, av = separa_ementa_bilingue("Texto PT com (Syllabus) no meio.")
    assert en is None and len(av) == 1, "'(Syllabus)' no meio do parágrafo deveria virar aviso"

    print("demo ok — identificação, contexto_disciplinas, competências (5col/4col/3tabelas), alinhamento (4col/3col), cronograma (4col/3col), bibliografia, headings em inglês e Ementa bilíngue extraídos corretamente")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
