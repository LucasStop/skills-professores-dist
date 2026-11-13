#!/usr/bin/env python3
"""Consulta dados institucionais do PPC do curso BSI (ANEXO A e Matriz de Competências).

Permite consultar os dados oficiais de disciplinas (Ementa, Temas de Estudo,
Bibliografias Básica e Complementar, Justificativa) a partir de
`references/ppc-bsi-anexo-a.json`, sugerir disciplinas precedentes e posteriores
a partir de `references/matriz-competencias-bsi.json` (Figura 9 do PPC),
e conferir as pendências de aprovação do NDE em relação ao PPC oficial
a partir do arquivo de dados do plano de ensino (`--confere dados.json`).

Uso:
    python3 consulta_ppc.py "<disciplina>"                 # Ementa, Temas, Bibliografias (ANEXO A)
    python3 consulta_ppc.py --precedencia "<disciplina>"   # Precedentes/posteriores (Matriz)
    python3 consulta_ppc.py --confere dados.json           # Confere pendências do NDE contra o PPC
    python3 consulta_ppc.py --demo

Saída sempre JSON em stdout (`ensure_ascii=False`, `indent=2`) contendo a chave `avisos`.

Regras de negócio:
1. Casamento de nomes tolerante e sem similaridade difusa:
   - Igualdade normalizada (minúsculas, sem acentos, sem pontuação, espaços colapsados);
   - Igualdade de conjunto de palavras (resolve ordem trocada, ex.: "Inovação e Empreendedorismo"
     vs "Empreendedorismo e Inovação");
   - Dicionário explícito `APELIDOS` para divergências de sigla ("Clínica de TIC"), hifenização
     ("Ciber-Físicos"), gerúndio ("Implementando" vs "Implementação"), truncamento ("em Computação")
     e erros de digitação institucionais ("Tunning", "Perfomance").
   - Ambiguidade ou termo não encontrado nunca decide sozinho: devolve campos nulos e aviso com os
     candidatos mais próximos por palavras em comum.
2. Precedência:
   - Para disciplina X no período P com contribuição em um elemento de competência (EC):
     - Precedente: disciplina de período < P que Internaliza (I) o mesmo EC;
     - Posterior: disciplina de período > P que Mobiliza (M) ou Certifica (C) o mesmo EC.
   - Disciplinas agregadas sem duplicatas, ordenadas por período e nome.
   - 1º período nunca tem precedente; 8º período nunca tem posterior.
   - As precedências são sempre sugestões para confirmação do professor (aviso fixo).
"""
import json
import os
import re
import sys
import unicodedata

DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIR_REFERENCES = os.path.join(DIR_ATUAL, "..", "references")
CAMINHO_PADRAO_ANEXO_A = os.path.join(DIR_REFERENCES, "ppc-bsi-anexo-a.json")
CAMINHO_PADRAO_MATRIZ = os.path.join(DIR_REFERENCES, "matriz-competencias-bsi.json")

# Stopwords desconsideradas na busca de candidatos por palavras em comum
STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "pela", "pelas",
    "pelo", "pelos", "por", "seus", "suas",
}

# Dicionário explícito de apelidos e divergências entre Matriz, ANEXO A e nomes usuais.
# Mapeia formas normalizadas da variante para a forma normalizada canônica.
APELIDOS = {
    # Clínica de TIC (Matriz) vs Clínica de Tecnologia da Informação e Comunicação (ANEXO A)
    "clinica de tic": "clinica de tecnologia da informacao e comunicacao",
    # Ciber-Físicos com hífen (Matriz) vs Ciberfisicos sem hífen (ANEXO A)
    "fundamentos de sistemas ciber fisicos": "fundamentos de sistemas ciberfisicos",
    "conectividade de sistemas ciber fisicos": "conectividade de sistemas ciberfisicos",
    # Performance (Matriz) vs Perfomance com erro de digitação institucional no ANEXO A
    "performance em sistemas ciber fisicos": "perfomance em sistemas ciberfisicos",
    "performance em sistemas ciberfisicos": "perfomance em sistemas ciberfisicos",
    "perfomance em sistemas ciber fisicos": "perfomance em sistemas ciberfisicos",
    # Implementação (Matriz) vs Implementando (ANEXO A)
    "experiencia criativa implementacao de sistemas de informacao": "experiencia criativa implementando sistemas de informacao",
    # Tunning com dois 'n' (Matriz) vs Tuning* (ANEXO A)
    "database performance tunning": "database performance tuning",
    # Resolução de Problemas Estruturados (Matriz) vs sufixo 'em Computação' (ANEXO A)
    "resolucao de problemas estruturados": "resolucao de problemas estruturados em computacao",
    # Negócio no singular (Matriz) vs Negócios no plural (ANEXO A)
    "inovacao nos processos de negocio": "inovacao nos processos de negocios",
}

# Mapeamento bidirecional derivado automaticamente
_APELIDOS_BIDIRECIONAL = {}
for _k, _v in APELIDOS.items():
    _APELIDOS_BIDIRECIONAL[_k] = _v
    if _v not in _APELIDOS_BIDIRECIONAL:
        _APELIDOS_BIDIRECIONAL[_v] = _k

# Lista de disciplinas da Matriz que não possuem par legítimo no ANEXO A.
# No BSI, todos os 44 pares possuem correspondência real comprovada; a lista permanece vazia.
SEM_PAR = []


def normaliza(texto):
    """Normaliza texto: minúsculas, remove acentuação, pontuação e colapsa espaços."""
    if not texto:
        return ""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    sem_pontuacao = re.sub(r"[^\w\s]", " ", sem_acento.lower())
    return re.sub(r"\s+", " ", sem_pontuacao).strip()


def palavras(texto):
    """Retorna conjunto de todas as palavras normalizadas do texto."""
    return set(normaliza(texto).split())


def palavras_significativas(texto):
    """Retorna conjunto de palavras significativas (sem stopwords)."""
    pw = {w for w in normaliza(texto).split() if w not in STOPWORDS}
    return pw or palavras(texto)


def candidatos_por_palavras_em_comum(termo, lista_nomes):
    """Retorna os nomes de `lista_nomes` que compartilham mais palavras significativas com `termo`."""
    pw = palavras_significativas(termo)
    if not pw:
        return []
    pontuados = []
    for nome in lista_nomes:
        nw = palavras_significativas(nome)
        inter = pw & nw
        if inter:
            pontuados.append((len(inter), nome))
    if not pontuados:
        return []
    pontuados.sort(key=lambda item: (-item[0], item[1]))
    max_score = pontuados[0][0]
    return [nome for score, nome in pontuados if score == max_score]


def carrega_anexo_a(caminho=None):
    """Carrega dados do ANEXO A extraído do PPC."""
    caminho = caminho or CAMINHO_PADRAO_ANEXO_A
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def carrega_matriz(caminho=None):
    """Carrega dados da Matriz de Competências (Figura 9 do PPC)."""
    caminho = caminho or CAMINHO_PADRAO_MATRIZ
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def casa_disciplina(termo, lista_disciplinas, extrai_nome):
    """Busca tolerante e sem similaridade difusa.

    Retorna tupla `(item, candidatos)`:
    - Se encontrar correspondência inequívoca: `(item, None)`
    - Se ambíguo ou não encontrado: `(None, candidatos_proximos)`
    """
    if not termo or not termo.strip():
        return None, []

    norm_termo = normaliza(termo)
    pal_termo = palavras(termo)
    todos_nomes = [extrai_nome(d) for d in lista_disciplinas]

    # 1. Igualdade normalizada exata
    iguais_norm = [d for d in lista_disciplinas if normaliza(extrai_nome(d)) == norm_termo]
    if len(iguais_norm) == 1:
        return iguais_norm[0], None
    if len(iguais_norm) > 1:
        return None, [extrai_nome(d) for d in iguais_norm]

    # 2. Mesmo conjunto de palavras (resolve ordem trocada)
    iguais_palavras = [d for d in lista_disciplinas if palavras(extrai_nome(d)) == pal_termo]
    if len(iguais_palavras) == 1:
        return iguais_palavras[0], None
    if len(iguais_palavras) > 1:
        return None, [extrai_nome(d) for d in iguais_palavras]

    # 3. Mapeamento explícito de apelidos / divergências
    alias_norm = _APELIDOS_BIDIRECIONAL.get(norm_termo)
    if alias_norm:
        alias_words = set(alias_norm.split())
        candidatos_alias = [
            d for d in lista_disciplinas
            if normaliza(extrai_nome(d)) == alias_norm or palavras(extrai_nome(d)) == alias_words
        ]
        if len(candidatos_alias) == 1:
            return candidatos_alias[0], None
        if len(candidatos_alias) > 1:
            return None, [extrai_nome(d) for d in candidatos_alias]

    # Também checa se o nome da disciplina cadastrada aponta para o termo buscado via apelido
    candidatos_rev = [
        d for d in lista_disciplinas
        if _APELIDOS_BIDIRECIONAL.get(normaliza(extrai_nome(d))) == norm_termo
    ]
    if len(candidatos_rev) == 1:
        return candidatos_rev[0], None
    if len(candidatos_rev) > 1:
        return None, [extrai_nome(d) for d in candidatos_rev]

    # 4. Não encontrado: computa candidatos mais próximos por palavras em comum
    candidatos = candidatos_por_palavras_em_comum(termo, todos_nomes)
    return None, candidatos


def consulta_ementa(termo, caminho_anexo=None):
    """Consulta dados de uma disciplina no ANEXO A do PPC.

    Retorna dict com chaves `disciplina`, `periodo`, `ementa`, `temas_estudo`,
    `bibliografia_basica`, `bibliografia_complementar`, `justificativa`, `avisos`.
    """
    dados_anexo = carrega_anexo_a(caminho_anexo)
    disciplinas = dados_anexo.get("disciplinas", [])

    item, candidatos = casa_disciplina(termo, disciplinas, lambda d: d["DISCIPLINA"])

    if item is None:
        avisos = [
            f"disciplina '{termo}' não encontrada no ANEXO A do PPC; peça o texto institucional (ementa, temas, bibliografia) ao professor/NDE"
        ]
        if candidatos:
            avisos.append(
                f"candidatos mais próximos por palavra em comum: {', '.join(sorted(candidatos))}"
            )
        resultado = {
            "disciplina": None,
            "periodo": None,
            "ementa": None,
            "temas_estudo": None,
            "bibliografia_basica": None,
            "bibliografia_complementar": None,
            "justificativa": None,
            "avisos": avisos,
        }
        if len(candidatos) == 1:
            resultado["sugestao"] = candidatos[0]
        return resultado

    periodo_str = item.get("PERIODO", "")
    try:
        periodo_int = int(re.sub(r"\D", "", periodo_str))
    except (ValueError, TypeError):
        periodo_int = None

    return {
        "disciplina": item.get("DISCIPLINA"),
        "periodo": periodo_int,
        "ementa": item.get("EMENTA"),
        "temas_estudo": item.get("TEMAS_ESTUDO"),
        "bibliografia_basica": item.get("BIBLIOGRAFIA_BASICA"),
        "bibliografia_complementar": item.get("BIBLIOGRAFIA_COMPLEMENTAR"),
        "justificativa": item.get("JUSTIFICATIVA"),
        "avisos": [],
    }


def consulta_precedencia(termo, caminho_matriz=None):
    """Deriva disciplinas precedentes e posteriores com base na Matriz de Competências.

    Regra de precedência:
    - Precedente: disciplina de período < P que Internaliza (I) o mesmo elemento de competência;
    - Posterior: disciplina de período > P que Mobiliza (M) ou Certifica (C) o mesmo elemento.

    Retorna dict com chaves `disciplina`, `periodo`, `precedentes`, `posteriores`, `avisos`.
    """
    dados_matriz = carrega_matriz(caminho_matriz)
    disciplinas = dados_matriz.get("disciplinas", [])

    item, candidatos = casa_disciplina(termo, disciplinas, lambda d: d["disciplina"])

    if item is None:
        avisos = [
            f"disciplina '{termo}' não encontrada na Matriz de Competências do PPC; peça as informações ao professor/NDE"
        ]
        if candidatos:
            avisos.append(
                f"candidatos mais próximos por palavra em comum: {', '.join(sorted(candidatos))}"
            )
        resultado = {
            "disciplina": None,
            "periodo": None,
            "precedentes": [],
            "posteriores": [],
            "avisos": avisos,
        }
        # ponytail: so um candidato vira sugestão; ambiguidade (2+) continua só no aviso
        if len(candidatos) == 1:
            resultado["sugestao"] = candidatos[0]
        return resultado

    periodo_alvo = item["periodo"]
    nome_alvo = item["disciplina"]
    ecs_alvo = set(item.get("elementos", {}).keys())

    precedentes_map = {}
    posteriores_map = {}

    for outra in disciplinas:
        p_outra = outra["periodo"]
        nome_outra = outra["disciplina"]
        elems_outra = outra.get("elementos", {})

        # Precedente: período < P e Internaliza (I) o mesmo EC
        if p_outra < periodo_alvo:
            for ec in ecs_alvo:
                if elems_outra.get(ec) == "Internaliza":
                    if nome_outra not in precedentes_map:
                        precedentes_map[nome_outra] = {
                            "disciplina": nome_outra,
                            "periodo": p_outra,
                            "elementos": set(),
                        }
                    precedentes_map[nome_outra]["elementos"].add(ec)

        # Posterior: período > P e Mobiliza (M) ou Certifica (C) o mesmo EC
        if p_outra > periodo_alvo:
            for ec in ecs_alvo:
                if elems_outra.get(ec) in ("Mobiliza", "Certifica"):
                    if nome_outra not in posteriores_map:
                        posteriores_map[nome_outra] = {
                            "disciplina": nome_outra,
                            "periodo": p_outra,
                            "elementos": set(),
                        }
                    posteriores_map[nome_outra]["elementos"].add(ec)

    def _formata_lista(mapa):
        ordenados = sorted(mapa.values(), key=lambda x: (x["periodo"], x["disciplina"]))
        return [
            {
                "disciplina": it["disciplina"],
                "periodo": it["periodo"],
                "elementos": sorted(list(it["elementos"])),
            }
            for it in ordenados
        ]

    avisos = [
        "As disciplinas precedentes e posteriores são sugestões automáticas baseadas na Matriz de Competências (Figura 9 do PPC) e devem ser confirmadas pelo professor."
    ]

    return {
        "disciplina": nome_alvo,
        "periodo": periodo_alvo,
        "precedentes": _formata_lista(precedentes_map),
        "posteriores": _formata_lista(posteriores_map),
        "avisos": avisos,
    }


def cruza_matriz_anexo(matriz_disciplinas, anexo_disciplinas):
    """Cruza as disciplinas da Matriz com as do ANEXO A e devolve as que não casam."""
    nao_casam = []
    for d_matriz in matriz_disciplinas:
        item, _ = casa_disciplina(d_matriz["disciplina"], anexo_disciplinas, lambda a: a["DISCIPLINA"])
        if item is None:
            nao_casam.append(d_matriz["disciplina"])
    return nao_casam


def normaliza_espacos(texto):
    """Normaliza apenas espaços e quebras de linha (sem alterar palavras, caixa ou acentos)."""
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def extrai_valores_plano(dados):
    """Extrai o dicionário de valores de um JSON de plano (formato extrator ou preencher_template)."""
    if isinstance(dados, str):
        with open(dados, encoding="utf-8") as f:
            dados = json.load(f)
    if not isinstance(dados, dict):
        return {}
    if "dados" in dados and isinstance(dados["dados"], dict):
        dados = dados["dados"]
    if "valores" in dados and isinstance(dados["valores"], dict):
        return dados["valores"]
    return dados


def confere_plano(dados_plano, caminho_anexo=None):
    """Confere seções do plano de ensino contra o PPC institucional (ANEXO A).

    Analisa Ementa, Contexto e Competências:
    - Ementa idêntica à do PPC após normalização de espaços/quebras de linha: pré-aprovada;
    - Ementa divergente: pendência de revisão do NDE com resumo curto da diferença de palavras;
    - Ementa ausente no plano: pendência do NDE;
    - Contexto e Competências: sempre pendência com motivo 'sem texto de referência no PPC';
    - Disciplina fora do dataset: todas as seções viram pendência do NDE + aviso.

    Retorna dict com chaves `disciplina`, `pendencias_nde`, `pre_aprovadas`, `avisos`.
    """
    valores = extrai_valores_plano(dados_plano)

    nome_disciplina = (
        valores.get("DISCIPLINA")
        or valores.get("disciplina")
        or valores.get("Nome")
        or valores.get("DISCIPLINA_NOME")
    )
    if isinstance(nome_disciplina, str):
        nome_disciplina = nome_disciplina.strip()

    ementa_plano = valores.get("EMENTA") or valores.get("ementa") or ""
    if isinstance(ementa_plano, str):
        ementa_plano = ementa_plano.strip()
    else:
        ementa_plano = ""

    dados_anexo = carrega_anexo_a(caminho_anexo)
    disciplinas_anexo = dados_anexo.get("disciplinas", [])

    item, candidatos = casa_disciplina(
        nome_disciplina or "", disciplinas_anexo, lambda d: d["DISCIPLINA"]
    )

    pendencias_nde = []
    pre_aprovadas = []
    avisos = []

    if item is None:
        pendencias_nde.append({"secao": "Ementa", "motivo": "sem texto de referência no PPC"})
        pendencias_nde.append({"secao": "Contexto", "motivo": "sem texto de referência no PPC"})
        pendencias_nde.append({"secao": "Competências", "motivo": "sem texto de referência no PPC"})

        if nome_disciplina:
            avisos.append(
                f"disciplina '{nome_disciplina}' não encontrada no PPC BSI; todas as seções são pendências do NDE"
            )
            if candidatos:
                avisos.append(
                    f"candidatos mais próximos por palavra em comum no PPC: {', '.join(sorted(candidatos))}"
                )
        else:
            avisos.append("nome da disciplina não informado no plano de ensino; todas as seções são pendências do NDE")

        return {
            "disciplina": nome_disciplina,
            "pendencias_nde": pendencias_nde,
            "pre_aprovadas": pre_aprovadas,
            "avisos": avisos,
        }

    nome_oficial = item.get("DISCIPLINA")
    ementa_ppc = (item.get("EMENTA") or "").strip()

    # 1. Conferência da Ementa
    if not ementa_plano:
        pendencias_nde.append({
            "secao": "Ementa",
            "motivo": "Ementa ausente no plano de ensino",
        })
    else:
        norm_plano = normaliza_espacos(ementa_plano)
        norm_ppc = normaliza_espacos(ementa_ppc)
        if norm_plano == norm_ppc:
            pre_aprovadas.append("Ementa")
        else:
            pal_plano = norm_plano.split()
            pal_ppc = norm_ppc.split()
            diff = len(pal_plano) - len(pal_ppc)
            if diff > 0:
                resumo = f"{diff} palavra{'s' if diff > 1 else ''} a mais que o PPC"
            elif diff < 0:
                resumo = f"{abs(diff)} palavra{'s' if abs(diff) > 1 else ''} a menos que o PPC"
            else:
                resumo = "mesma contagem de palavras, mas com alterações no texto"
            pendencias_nde.append({
                "secao": "Ementa",
                "motivo": f"Ementa difere do PPC ({resumo})",
            })

    # 2. Contexto e Competências: sempre pendência com motivo "sem texto de referência no PPC"
    pendencias_nde.append({
        "secao": "Contexto",
        "motivo": "sem texto de referência no PPC",
    })
    pendencias_nde.append({
        "secao": "Competências",
        "motivo": "sem texto de referência no PPC",
    })

    return {
        "disciplina": nome_oficial,
        "pendencias_nde": pendencias_nde,
        "pre_aprovadas": pre_aprovadas,
        "avisos": avisos,
    }


def demo():
    """Valida o funcionamento de consulta_ementa, consulta_precedencia e casamento de nomes."""
    dados_anexo = carrega_anexo_a()
    dados_matriz = carrega_matriz()
    disc_anexo = dados_anexo["disciplinas"]
    disc_matriz = dados_matriz["disciplinas"]

    assert len(disc_anexo) == 44, f"Esperado 44 disciplinas no ANEXO A, obtido {len(disc_anexo)}"
    assert len(disc_matriz) == 44, f"Esperado 44 disciplinas na Matriz, obtido {len(disc_matriz)}"

    # 1. Nome exato, sem acento/caixa diferente e com ordem trocada acham a mesma disciplina
    d_exata = consulta_ementa("Empreendedorismo e Inovação em Sistemas de Informação")
    d_sem_acento = consulta_ementa("empreendedorismo e inovacao em sistemas de informacao")
    d_ordem_trocada = consulta_ementa("Inovação e Empreendedorismo em Sistemas de Informação")

    assert d_exata["disciplina"] == "Empreendedorismo e Inovação em Sistemas de Informação"
    assert d_sem_acento["disciplina"] == d_exata["disciplina"]
    assert d_ordem_trocada["disciplina"] == d_exata["disciplina"]
    assert d_exata["periodo"] == 7
    assert d_exata["ementa"] and d_exata["ementa"] == d_sem_acento["ementa"] == d_ordem_trocada["ementa"]
    assert d_exata["avisos"] == []

    # Também confere casamento com apelido (Clínica de TIC vs por extenso)
    d_apelido = consulta_ementa("Clínica de TIC")
    assert d_apelido["disciplina"] == "Clínica de Tecnologia da Informação e Comunicação"
    assert d_apelido["periodo"] == 3

    # 2. Disciplina inexistente: campos nulos + aviso
    d_inexistente = consulta_ementa("Compiladores e Teoria da Computação")
    assert d_inexistente["disciplina"] is None
    assert d_inexistente["periodo"] is None
    assert d_inexistente["ementa"] is None
    assert d_inexistente["temas_estudo"] is None
    assert d_inexistente["bibliografia_basica"] is None
    assert d_inexistente["bibliografia_complementar"] is None
    assert d_inexistente["justificativa"] is None
    assert len(d_inexistente["avisos"]) >= 1
    assert "não encontrada no ANEXO A" in d_inexistente["avisos"][0]

    p_inexistente = consulta_precedencia("Compiladores e Teoria da Computação")
    assert p_inexistente["disciplina"] is None
    assert p_inexistente["periodo"] is None
    assert p_inexistente["precedentes"] == []
    assert p_inexistente["posteriores"] == []
    assert len(p_inexistente["avisos"]) >= 1

    # Candidato único por palavra em comum vira sugestão explícita (disciplina continua null)
    p_sugestao = consulta_precedencia("Engenharia de Software")
    assert p_sugestao["disciplina"] is None
    assert p_sugestao["sugestao"] == "Métodos e Ferramentas de Engenharia de Software"

    # Busca ambígua/parcial não decide sozinha: devolve nulos e lista candidatos
    d_ambigua = consulta_ementa("Experiência Criativa")
    assert d_ambigua["disciplina"] is None
    assert any("candidatos mais próximos por palavra em comum" in a for a in d_ambigua["avisos"])

    # 3. Precedência: 1º período (precedentes == []), último período (posteriores == []), intermediária conferida
    p_p1 = consulta_precedencia("Raciocínio Algorítmico")
    assert p_p1["periodo"] == 1
    assert p_p1["precedentes"] == [], "Disciplina do 1º período não pode ter precedentes"
    assert len(p_p1["posteriores"]) > 0

    p_p8 = consulta_precedencia("Governança de Tecnologia da Informação")
    assert p_p8["periodo"] == 8
    assert p_p8["posteriores"] == [], "Disciplina do 8º período não pode ter posteriores"
    assert len(p_p8["precedentes"]) > 0

    # Intermediária conferida à mão contra a Matriz: Banco de Dados (P2)
    # Na Matriz: Banco de Dados contribui com B1 (Internaliza), B2 (Internaliza), B3 (Internaliza).
    # - Precedente em P1: 'Desenvolvimento de Carreira' (P1) Internaliza B1 -> justifica como precedente via B1.
    #   'Experiência Criativa: Navegando Pelos Sistemas de Informação' (P1) Internaliza B1 e B2 -> justifica via B1, B2.
    # - Posterior em P7: 'Gestão de Projetos de TI' (P7) Mobiliza/Certifica B1 -> justifica como posterior via B1.
    p_bd = consulta_precedencia("Banco de Dados")
    assert p_bd["periodo"] == 2
    precs_bd_nomes = {x["disciplina"]: x["elementos"] for x in p_bd["precedentes"]}
    assert "Desenvolvimento de Carreira" in precs_bd_nomes
    assert "B1" in precs_bd_nomes["Desenvolvimento de Carreira"]
    assert "Experiência Criativa: Navegando Pelos Sistemas de Informação" in precs_bd_nomes
    assert set(precs_bd_nomes["Experiência Criativa: Navegando Pelos Sistemas de Informação"]) == {"B1", "B2"}

    posts_bd_nomes = {x["disciplina"]: x["elementos"] for x in p_bd["posteriores"]}
    assert "Gestão de Projetos de TI" in posts_bd_nomes
    assert "B1" in posts_bd_nomes["Gestão de Projetos de TI"]

    # 4. Invariantes para todas as 44 disciplinas da Matriz:
    # - Nenhuma aparece como precedente/posterior de si mesma;
    # - Nenhum precedente tem período >= P;
    # - Nenhum posterior tem período <= P;
    # - Disciplinas do 1º período nunca têm precedentes; do 8º nunca têm posteriores.
    for disc in disc_matriz:
        nome = disc["disciplina"]
        periodo = disc["periodo"]
        resultado = consulta_precedencia(nome)
        assert resultado["disciplina"] == nome
        assert resultado["periodo"] == periodo

        precs = resultado["precedentes"]
        posts = resultado["posteriores"]

        if periodo == 1:
            assert precs == [], f"{nome} (P1) não deveria ter precedentes"
        if periodo == 8:
            assert posts == [], f"{nome} (P8) não deveria ter posteriores"

        for p in precs:
            assert p["disciplina"] != nome, f"{nome} não pode ser precedente de si mesma"
            assert p["periodo"] < periodo, f"Precedente {p['disciplina']} (P{p['periodo']}) deve ter período < {periodo}"
            assert len(p["elementos"]) > 0

        for p in posts:
            assert p["disciplina"] != nome, f"{nome} não pode ser posterior de si mesma"
            assert p["periodo"] > periodo, f"Posterior {p['disciplina']} (P{p['periodo']}) deve ter período > {periodo}"
            assert len(p["elementos"]) > 0

    # 5. Cruzamento dos 44 nomes da Matriz com ANEXO A
    nao_casam_matriz_anexo = cruza_matriz_anexo(disc_matriz, disc_anexo)
    assert nao_casam_matriz_anexo == SEM_PAR, (
        f"Todas as 44 disciplinas deveriam casar via normalização ou APELIDOS; "
        f"não casaram: {nao_casam_matriz_anexo}"
    )

    # Verificação inversa: todas as 44 do ANEXO A casam na Matriz
    nao_casam_anexo_matriz = []
    for d_anexo in disc_anexo:
        item, _ = casa_disciplina(d_anexo["DISCIPLINA"], disc_matriz, lambda m: m["disciplina"])
        if item is None:
            nao_casam_anexo_matriz.append(d_anexo["DISCIPLINA"])
    assert nao_casam_anexo_matriz == [], f"Divergência inversa do ANEXO A para Matriz: {nao_casam_anexo_matriz}"

    # 6. Conferência de pendências do NDE (--confere)
    ementa_bd = consulta_ementa("Banco de Dados")["ementa"]

    # Caso 1: Ementa idêntica à do PPC (com espaços/quebras diferentes): pré-aprovada; Contexto e Competências pendentes
    dados_identica = {
        "valores": {
            "DISCIPLINA": "Banco de Dados",
            "EMENTA": "  \n\t" + ementa_bd.replace(" ", "\n  \t  ") + "  \n",
            "CONTEXTO": "Texto livre de contexto elaborado pelo professor.",
        }
    }
    res_identica = confere_plano(dados_identica)
    assert res_identica["disciplina"] == "Banco de Dados"
    assert res_identica["pre_aprovadas"] == ["Ementa"]
    assert len(res_identica["pendencias_nde"]) == 2
    secoes_identica = [p["secao"] for p in res_identica["pendencias_nde"]]
    assert secoes_identica == ["Contexto", "Competências"]
    assert all(p["motivo"] == "sem texto de referência no PPC" for p in res_identica["pendencias_nde"])
    assert res_identica["avisos"] == []

    # Validação do formato encapsulado {"dados": {"valores": ...}} retornado pelo extrator
    res_identica_extrator = confere_plano({"dados": dados_identica})
    assert res_identica_extrator["pre_aprovadas"] == ["Ementa"]
    assert len(res_identica_extrator["pendencias_nde"]) == 2

    # Caso 2: Ementa com uma frase a mais: pendência com motivo
    dados_frase_a_mais = {
        "valores": {
            "DISCIPLINA": "Banco de Dados",
            "EMENTA": ementa_bd + " Serão abordados tópicos complementares avançados de NoSQL.",
        }
    }
    res_frase_a_mais = confere_plano(dados_frase_a_mais)
    assert res_frase_a_mais["pre_aprovadas"] == []
    assert len(res_frase_a_mais["pendencias_nde"]) == 3
    p_ementa = next(p for p in res_frase_a_mais["pendencias_nde"] if p["secao"] == "Ementa")
    assert "Ementa difere do PPC" in p_ementa["motivo"]
    assert "palavras a mais" in p_ementa["motivo"]
    p_outras = [p for p in res_frase_a_mais["pendencias_nde"] if p["secao"] != "Ementa"]
    assert len(p_outras) == 2
    assert all(p["motivo"] == "sem texto de referência no PPC" for p in p_outras)

    # Caso 3: Sem Ementa: pendência
    dados_sem_ementa = {
        "valores": {
            "DISCIPLINA": "Banco de Dados",
            "EMENTA": "   ",
        }
    }
    res_sem_ementa = confere_plano(dados_sem_ementa)
    assert res_sem_ementa["pre_aprovadas"] == []
    p_ementa_ausente = next(p for p in res_sem_ementa["pendencias_nde"] if p["secao"] == "Ementa")
    assert "Ementa ausente" in p_ementa_ausente["motivo"]

    # Também se a chave EMENTA não for fornecida no dicionário
    res_chave_ausente = confere_plano({"valores": {"DISCIPLINA": "Banco de Dados"}})
    assert res_chave_ausente["pre_aprovadas"] == []
    assert any(p["secao"] == "Ementa" and "Ementa ausente" in p["motivo"] for p in res_chave_ausente["pendencias_nde"])

    # Caso 4: Disciplina inexistente: tudo pendente + aviso
    dados_inexistente = {
        "valores": {
            "DISCIPLINA": "Disciplina Inexistente XPTO",
            "EMENTA": "Estudo de conceitos não previstos em curso algum.",
        }
    }
    res_inexistente = confere_plano(dados_inexistente)
    assert res_inexistente["disciplina"] == "Disciplina Inexistente XPTO"
    assert res_inexistente["pre_aprovadas"] == []
    assert len(res_inexistente["pendencias_nde"]) == 3
    secoes_in = [p["secao"] for p in res_inexistente["pendencias_nde"]]
    assert secoes_in == ["Ementa", "Contexto", "Competências"]
    assert all(p["motivo"] == "sem texto de referência no PPC" for p in res_inexistente["pendencias_nde"])
    assert len(res_inexistente["avisos"]) >= 1
    assert "não encontrada no PPC BSI" in res_inexistente["avisos"][0]

    print(
        f"demo ok — casamento de nomes (exato, normalizado, palavras, apelidos), "
        f"consulta simples, precedência e conferência de pendências NDE validados para as 44 disciplinas sem sobra"
    )


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
        return

    if len(sys.argv) == 3 and sys.argv[1] == "--precedencia":
        resultado = consulta_precedencia(sys.argv[2])
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return

    if len(sys.argv) == 3 and sys.argv[1] == "--confere":
        caminho_dados = sys.argv[2]
        if not os.path.exists(caminho_dados):
            print(f"Erro: arquivo '{caminho_dados}' não encontrado.", file=sys.stderr)
            sys.exit(1)
        resultado = confere_plano(caminho_dados)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return

    if len(sys.argv) == 2 and not sys.argv[1].startswith("--"):
        resultado = consulta_ementa(sys.argv[1])
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return

    print(
        "Uso:\n"
        "  python3 consulta_ppc.py \"<disciplina>\"                 # Ementa, Temas, Bibliografias (ANEXO A)\n"
        "  python3 consulta_ppc.py --precedencia \"<disciplina>\"   # Precedentes/posteriores (Matriz)\n"
        "  python3 consulta_ppc.py --confere <dados.json>         # Confere pendências do NDE contra o PPC\n"
        "  python3 consulta_ppc.py --demo",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
