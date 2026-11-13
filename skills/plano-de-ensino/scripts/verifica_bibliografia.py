#!/usr/bin/env python3
"""Busca referências no catálogo Pergamum (biblioteca PUCPR) e periódicos de
acesso aberto no DOAJ (Directory of Open Access Journals), além de conferir os
mínimos de bibliografia exigidos pelo NDE no template oficial da PUCPR
(Básica: no mínimo 3 títulos de livros + 1 periódico; Complementar: no mínimo 5
títulos de livros + 1 periódico — ver `references/template-pucpr.md` seção 6).

Só biblioteca padrão do Python — sem pip install. A busca usa a API pública
do Pergamum e a API pública do DOAJ (sem chave/login).

Uso:
    python3 verifica_bibliografia.py --busca "termo ou tema"
    python3 verifica_bibliografia.py --periodico "tema"
    python3 verifica_bibliografia.py --checa biblio_basica.json biblio_complementar.json
    python3 verifica_bibliografia.py --smoke
    python3 verifica_bibliografia.py --relatorio-ppc <ppc-bsi-anexo-a.json>
    python3 verifica_bibliografia.py --demo

`--busca` busca livros no catálogo Pergamum da PUCPR e retorna lista de candidatos.
`--periodico` busca periódicos científicos de acesso aberto no DOAJ por tema.
`--checa` valida os mínimos de livros e a presença/tipo de periódicos por bloco.
`--smoke` valida conectividade pontual com o Pergamum e o DOAJ.
`--relatorio-ppc` avalia a cobertura do Pergamum para referências reais do PPC.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

PERGAMUM_URL = "https://pergamum-biblioteca.pucpr.br/api/consulta"
DOAJ_URL = "https://doaj.org/api/search/journals"


def busca_pergamum(termo, page=1, per_page=20, timeout=4):
    """GET na API pública do Pergamum (busca livre).
    Retorna lista de registros normalizados via classifica_registro(), ou
    None se a rede falhar (sem internet, API fora do ar) — quem chama
    decide o fallback (pedir a lista manual ao professor). User-Agent
    explícito por precaução, mesmo padrão de busca_feriados_nacionais() em
    gerar_cronograma.py."""
    params = {
        "termo_pesquisa": termo,
        "coluna_um": "LIVRE",
        "search_tab": "pesquisa_geral",
        "search_id": str(int(time.time() * 1000)),
        "page": page,
        "perPage": per_page,
        "orderBy": "ano_publicacao",
        "direction": "D",
    }
    url = f"{PERGAMUM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        registros = dados if isinstance(dados, list) else dados.get("registros", [])
        return [classifica_registro(r) for r in registros]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        return None


def classifica_registro(registro):
    """Normaliza um registro cru do Pergamum pros campos que a bibliografia
    do plano de ensino usa. Função pura, não decide nada — só extrai/tipa."""
    cod_acervo = registro.get("cod_acervo", "")
    tipo = f"{registro.get('desc_tipo_obra', '')} {registro.get('classificacao', '')}".lower()
    return {
        "cod_acervo": cod_acervo,
        "referencia": (registro.get("referencia_sem_tag") or "").strip(),
        "obra": (registro.get("obra") or "").strip(),
        "link": f"https://pergamum-biblioteca.pucpr.br/acervo/{cod_acervo}" if cod_acervo else None,
        "e_virtual": "e-book" in tipo or "biblioteca virtual" in tipo or "online" in tipo,
        "tot_exemplares": int(registro.get("tot_exemplares") or 0),
        "autor": (registro.get("autor") or "").strip(),
        "ano": registro.get("ano_publicacao"),
    }


def busca_doaj(tema, per_page=10):
    """GET na API pública do DOAJ (Directory of Open Access Journals).
    Retorna lista de periódicos normalizados via classifica_periodico(), ou
    None se a rede falhar. Mesmo padrão de busca_pergamum."""
    url = f"{DOAJ_URL}/{urllib.parse.quote(tema)}?pageSize={per_page}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        return [classifica_periodico(r) for r in dados.get("results", [])]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        return None


def classifica_periodico(registro):
    """Normaliza um registro cru do DOAJ pros campos que o plano de ensino usa.
    Função pura, não decide nada — só extrai/tipa."""
    bib = registro.get("bibjson") if isinstance(registro, dict) and "bibjson" in registro else registro
    if not isinstance(bib, dict):
        bib = {}
    pissn = bib.get("pissn")
    eissn = bib.get("eissn")
    issn_principal = pissn or eissn
    issns = [i for i in [pissn, eissn] if i]
    publisher = bib.get("publisher") or {}
    assuntos = [s.get("term") for s in bib.get("subject", []) if isinstance(s, dict) and s.get("term")]
    link = f"https://doaj.org/toc/{issn_principal}" if issn_principal else None

    return {
        "titulo": (bib.get("title") or "").strip(),
        "issn": issn_principal,
        "issns": issns,
        "editora": (publisher.get("name") or "").strip(),
        "pais": (publisher.get("country") or "").strip(),
        "idiomas": bib.get("language") or [],
        "assuntos": assuntos,
        "link": link,
        "periodico": True,
        "acesso_aberto_doaj": True,
    }


def checa_minimos(basica, complementar):
    """basica/complementar: listas de itens já confirmados pelo professor,
    no formato de classifica_registro() (livros/e-books) e/ou
    classifica_periodico() (periódicos). Retorna avisos (lista de str) —
    nunca bloqueia, quem resolve é o professor."""
    avisos = []

    livros_basica = [item for item in basica if not item.get("periodico")]
    periodicos_basica = [item for item in basica if item.get("periodico")]

    livros_compl = [item for item in complementar if not item.get("periodico")]
    periodicos_compl = [item for item in complementar if item.get("periodico")]

    if len(livros_basica) < 3:
        avisos.append(f"Bibliografia Básica tem {len(livros_basica)} título(s), mínimo exigido é 3 (regra do NDE/template oficial)")
    if len(livros_compl) < 5:
        avisos.append(f"Bibliografia Complementar tem {len(livros_compl)} título(s), mínimo exigido é 5 (regra do NDE/template oficial)")

    if livros_basica and not any(item.get("e_virtual") for item in livros_basica):
        avisos.append("nenhum título da Básica está na biblioteca virtual — o template oficial prioriza títulos virtuais/com mais exemplares por estudante (preferência, não bloqueio)")

    for item in livros_compl:
        if item.get("cod_acervo") and item.get("tot_exemplares", 0) == 0:
            avisos.append(f"Complementar: \"{item['referencia'][:80]}\" não tem exemplar físico no acervo (tot_exemplares=0) — o template oficial exige ao menos 1 exemplar físico na Complementar")

    blocos = [
        ("Básica", periodicos_basica),
        ("Complementar", periodicos_compl),
    ]
    for nome_bloco, periodicos in blocos:
        if not periodicos:
            avisos.append(f"{nome_bloco}: falta o periódico obrigatório — o template oficial exige no mínimo 1 título de periódico por bloco")
        else:
            for p in periodicos:
                if not p.get("acesso_aberto_doaj"):
                    ref = p.get("titulo") or p.get("referencia") or "informado"
                    avisos.append(f"{nome_bloco}: periódico \"{ref}\" sem confirmação de acesso aberto no DOAJ — confirme manualmente a disponibilidade em texto completo nas bases com login institucional da PUC")

    return avisos


def smoke_test():
    """Faz 1 busca real no Pergamum e 1 no DOAJ e confere o formato esperado.
    Imprime ok/falhou por serviço e sai com código != 0 se algum falhar."""
    sucesso = True

    chaves_pergamum = {"cod_acervo", "referencia", "link", "e_virtual", "tot_exemplares", "autor", "ano"}
    try:
        res_pergamum = busca_pergamum("Sommerville", per_page=1)
        if res_pergamum and isinstance(res_pergamum, list) and len(res_pergamum) > 0 and chaves_pergamum.issubset(res_pergamum[0].keys()):
            print("Pergamum: ok")
        else:
            print("Pergamum: falhou")
            sucesso = False
    except Exception as e:
        print(f"Pergamum: falhou ({e})")
        sucesso = False

    chaves_doaj = {"titulo", "issn", "issns", "editora", "pais", "idiomas", "assuntos", "link", "periodico", "acesso_aberto_doaj"}
    try:
        res_doaj = busca_doaj("software engineering", per_page=1)
        if res_doaj and isinstance(res_doaj, list) and len(res_doaj) > 0 and chaves_doaj.issubset(res_doaj[0].keys()):
            print("DOAJ: ok")
        else:
            print("DOAJ: falhou")
            sucesso = False
    except Exception as e:
        print(f"DOAJ: falhou ({e})")
        sucesso = False

    sys.exit(0 if sucesso else 1)


def normaliza_texto(texto):
    """Remove acentuação e caracteres especiais, passando para minúsculas."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return re.sub(r"[^\w\s]", " ", sem_acento)


def separa_referencias_ppc(texto):
    """Separa as referências individuais do texto de bibliografia do PPC."""
    if not texto:
        return []
    padrao = re.compile(r"(?:^|(?<=\s))(\d{1,2})\.\s+")
    matches = list(padrao.finditer(texto))
    candidatos = []
    for m in matches:
        start, end = m.start(), m.end()
        num = int(m.group(1))
        depois = texto[end:end+20].strip()
        if re.match(r"^(?:ed\b|Ed\b|edição|Edição|recurso\b)", depois, re.IGNORECASE):
            continue
        antes = texto[max(0, start-30):start].strip()
        if re.search(r"(?:\*\*|\w)\s*$", antes) and re.match(r"^(?:Rio de Janeiro|São Paulo|GEN|Pearson|Belo Horizonte|Porto Alegre|Curitiba)", depois):
            continue
        candidatos.append((start, end, num))

    itens = []
    for i in range(len(candidatos)):
        ini = candidatos[i][0]
        fim = candidatos[i+1][0] if i + 1 < len(candidatos) else len(texto)
        trecho = texto[ini:fim].strip()
        if trecho:
            itens.append(trecho)
    return itens


def extrai_autor_e_titulo(ref_str):
    """Extrai primeiro sobrenome do autor, início do título e título completo de uma referência."""
    ref = re.sub(r"^\d+\.\s*", "", ref_str).strip()
    m_bold = re.search(r"\*\*(.+?)\*\*", ref)
    if m_bold:
        titulo_raw = m_bold.group(1).strip()
        autor_raw = ref[:m_bold.start()].strip().rstrip(".,;:- ")
    else:
        partes = [p.strip() for p in ref.split(".") if p.strip()]
        if len(partes) >= 2:
            autor_raw = partes[0]
            titulo_raw = partes[1]
        else:
            autor_raw = ref
            titulo_raw = ""

    autor_limpo = re.sub(r"\*+", "", autor_raw).strip()
    primeiro_autor = re.split(r"[;,]|\be\b", autor_limpo)[0].strip()
    primeiro_autor = re.sub(r"\(.*?\)", "", primeiro_autor).strip()
    palavras_autor = primeiro_autor.split()
    sobrenome = palavras_autor[0] if palavras_autor else ""

    titulo_limpo = re.sub(r"\*+", "", titulo_raw).strip()
    titulo_principal = titulo_limpo.split(":")[0].strip()
    palavras_titulo = titulo_principal.split()
    inicio_titulo = " ".join(palavras_titulo[:3]) if palavras_titulo else ""

    return sobrenome, inicio_titulo, titulo_limpo


def titulo_compativel(tit_ref, obra_res, ref_res=""):
    """Verifica se o título da referência é compatível com o resultado do Pergamum."""
    norm_tit = normaliza_texto(tit_ref)
    norm_obra = normaliza_texto(obra_res)
    norm_ref = normaliza_texto(ref_res)

    stopwords = {"com", "para", "uma", "dos", "das", "que", "por", "sobre", "como", "aos"}
    palavras_ref = [p for p in norm_tit.split() if len(p) > 2 and p not in stopwords]
    if not palavras_ref:
        return norm_tit in norm_obra or norm_tit in norm_ref

    palavras_obra = set(norm_obra.split()) | set(norm_ref.split())
    matches = sum(1 for p in palavras_ref[:4] if p in palavras_obra)
    return matches >= min(2, len(palavras_ref))


def gera_relatorio_ppc(caminho_ppc, intervalo=0.5, timeout=4, orcamento_s=500):
    """Gera relatório de validação das referências do PPC no Pergamum.
    Cada requisição tem timeout curto e sem retry; passado o orçamento de
    tempo (orcamento_s), as referências restantes contam como erro."""
    inicio = time.time()
    with open(caminho_ppc, encoding="utf-8") as f:
        dados = json.load(f)

    disciplinas = dados.get("disciplinas", [])
    totais = {
        "basica": {"total": 0, "achadas": 0, "nao_achadas": 0, "erros": 0},
        "complementar": {"total": 0, "achadas": 0, "nao_achadas": 0, "erros": 0},
        "geral": {"total": 0, "achadas": 0, "nao_achadas": 0, "erros": 0, "taxa_acerto": 0.0},
    }
    nao_achadas = []

    for d in disciplinas:
        nome_disc = d.get("DISCIPLINA", "")
        blocos = [
            ("basica", "Básica", d.get("BIBLIOGRAFIA_BASICA")),
            ("complementar", "Complementar", d.get("BIBLIOGRAFIA_COMPLEMENTAR")),
        ]
        for chave_bloco, nome_bloco, texto_bloco in blocos:
            if not texto_bloco:
                continue
            refs = separa_referencias_ppc(texto_bloco)
            for ref in refs:
                totais[chave_bloco]["total"] += 1
                totais["geral"]["total"] += 1

                sobrenome, inicio_titulo, titulo_completo = extrai_autor_e_titulo(ref)
                termo = f"{sobrenome} {inicio_titulo}".strip()

                if intervalo > 0:
                    time.sleep(intervalo)

                if time.time() - inicio > orcamento_s:
                    resultados = None
                else:
                    resultados = busca_pergamum(termo, timeout=timeout)
                if resultados is None:
                    totais[chave_bloco]["erros"] += 1
                    totais["geral"]["erros"] += 1
                    continue

                achada = False
                sob_norm = normaliza_texto(sobrenome)
                for r in resultados:
                    aut_res = normaliza_texto(r.get("autor") or "")
                    ref_res = normaliza_texto(r.get("referencia") or "")
                    obra_res = normaliza_texto(r.get("obra") or "")
                    if sob_norm in aut_res or sob_norm in ref_res:
                        if titulo_compativel(titulo_completo or inicio_titulo, obra_res, ref_res):
                            achada = True
                            break

                if achada:
                    totais[chave_bloco]["achadas"] += 1
                    totais["geral"]["achadas"] += 1
                else:
                    totais[chave_bloco]["nao_achadas"] += 1
                    totais["geral"]["nao_achadas"] += 1
                    nao_achadas.append({
                        "disciplina": nome_disc,
                        "bloco": nome_bloco,
                        "termo_busca": termo,
                        "referencia": ref,
                    })

        total_validas = totais["geral"]["achadas"] + totais["geral"]["nao_achadas"]
        if total_validas > 0:
            totais["geral"]["taxa_acerto"] = round((totais["geral"]["achadas"] / total_validas) * 100, 2)
        try:
            with open("/tmp/relatorio_ppc.json", "w", encoding="utf-8") as f_prog:
                json.dump({"totais": totais, "nao_achadas": nao_achadas}, f_prog, ensure_ascii=False, indent=2)
        except OSError:
            pass

    return {"totais": totais, "nao_achadas": nao_achadas}


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--busca" and len(sys.argv) == 3:
        resultados = busca_pergamum(sys.argv[2])
        if resultados is None:
            print(json.dumps({"erro": "não consegui buscar no Pergamum (sem internet ou API fora do ar) — peça a lista de referências direto ao professor"}, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps({"resultados": resultados}, ensure_ascii=False, indent=2))
    elif len(sys.argv) >= 2 and sys.argv[1] == "--periodico" and len(sys.argv) == 3:
        resultados = busca_doaj(sys.argv[2])
        if resultados is None:
            print(json.dumps({"erro": "não consegui buscar no DOAJ (sem internet ou API fora do ar) — peça a sugestão de periódico direto ao professor"}, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps({"resultados": resultados}, ensure_ascii=False, indent=2))
    elif sys.argv[1:2] == ["--checa"] and len(sys.argv) == 4:
        with open(sys.argv[2], encoding="utf-8") as f:
            basica = json.load(f)
        with open(sys.argv[3], encoding="utf-8") as f:
            complementar = json.load(f)
        print(json.dumps({"avisos": checa_minimos(basica, complementar)}, ensure_ascii=False, indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == "--smoke":
        smoke_test()
    elif len(sys.argv) == 3 and sys.argv[1] == "--relatorio-ppc":
        relatorio = gera_relatorio_ppc(sys.argv[2])
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    else:
        print('uso: python3 verifica_bibliografia.py --busca "termo" | --periodico "tema" | --checa basica.json complementar.json | --smoke | --relatorio-ppc ppc.json', file=sys.stderr)
        sys.exit(1)


def demo():
    """python3 verifica_bibliografia.py --demo"""
    # 1. Registro do Pergamum
    registro_bruto = {
        "cod_acervo": "5337417",
        "desc_tipo_obra": "( E-books )",
        "obra": "Arquitetura completa de software: do desenvolvimento à maestria",
        "referencia_sem_tag": "BRANDÃO, Gustavo. Arquitetura completa de software: do desenvolvimento à maestria. São Paulo, SP: Casa do Código, 2026. 1 recurso online. ISBN 9788555194177.",
        "classificacao": "Online -  Biblioteca Virtual",
        "tot_exemplares": "0",
        "isbn_issn": "9788555194177 ",
        "autor": "Brandão, Gustavo ",
        "ano_publicacao": "2026",
    }
    item = classifica_registro(registro_bruto)
    assert item["cod_acervo"] == "5337417"
    assert item["link"] == "https://pergamum-biblioteca.pucpr.br/acervo/5337417"
    assert item["e_virtual"] is True, "e-book deveria ser classificado como virtual"
    assert item["tot_exemplares"] == 0
    assert item["referencia"].startswith("BRANDÃO, Gustavo.")
    assert item["obra"] == "Arquitetura completa de software: do desenvolvimento à maestria"

    registro_fisico = dict(registro_bruto, cod_acervo="9999", desc_tipo_obra="( Livros )", classificacao="Acervo Circulante", tot_exemplares="3")
    item_fisico = classifica_registro(registro_fisico)
    assert item_fisico["e_virtual"] is False
    assert item_fisico["tot_exemplares"] == 3

    # 2. Registros do DOAJ (incluindo caso com pissn+eissn e caso só com eissn)
    registro_doaj_ambos = {
        "id": "doaj-123",
        "bibjson": {
            "title": "Journal of Universal Computer Science",
            "pissn": "0948-695X",
            "eissn": "0948-6968",
            "publisher": {"name": "JUCS", "country": "AT"},
            "language": ["EN"],
            "subject": [{"term": "Computer science"}],
        },
    }
    item_doaj_ambos = classifica_periodico(registro_doaj_ambos)
    assert item_doaj_ambos["titulo"] == "Journal of Universal Computer Science"
    assert item_doaj_ambos["issn"] == "0948-695X"
    assert item_doaj_ambos["issns"] == ["0948-695X", "0948-6968"]
    assert item_doaj_ambos["editora"] == "JUCS"
    assert item_doaj_ambos["pais"] == "AT"
    assert item_doaj_ambos["idiomas"] == ["EN"]
    assert item_doaj_ambos["assuntos"] == ["Computer science"]
    assert item_doaj_ambos["link"] == "https://doaj.org/toc/0948-695X"
    assert item_doaj_ambos["periodico"] is True
    assert item_doaj_ambos["acesso_aberto_doaj"] is True

    registro_doaj_eissn = {
        "id": "doaj-456",
        "bibjson": {
            "title": "Journal of Internet and Software Engineering",
            "eissn": "2797-9016",
            "publisher": {"name": "Universitas Gadjah Mada", "country": "ID"},
            "language": ["EN", "ID"],
            "subject": [{"term": "Software engineering"}],
        },
    }
    item_doaj_eissn = classifica_periodico(registro_doaj_eissn)
    assert item_doaj_eissn["issn"] == "2797-9016"
    assert item_doaj_eissn["issns"] == ["2797-9016"]
    assert item_doaj_eissn["link"] == "https://doaj.org/toc/2797-9016"
    assert item_doaj_eissn["periodico"] is True
    assert item_doaj_eissn["acesso_aberto_doaj"] is True

    # 3. checa_minimos: lista incompleta de livros e sem periódicos -> avisos de títulos e de periódico por bloco
    avisos_incompleta = checa_minimos(basica=[item], complementar=[item_fisico])
    assert any("Básica tem 1" in a for a in avisos_incompleta), avisos_incompleta
    assert any("Complementar tem 1" in a for a in avisos_incompleta), avisos_incompleta
    assert any("Básica: falta o periódico" in a for a in avisos_incompleta), avisos_incompleta
    assert any("Complementar: falta o periódico" in a for a in avisos_incompleta), avisos_incompleta
    assert not any("biblioteca virtual" in a for a in avisos_incompleta), "básica já tem 1 item virtual"

    # 4. checa_minimos: 3 livros na Básica + 1 periódico DOAJ e 5 livros na Complementar + 1 periódico DOAJ -> zero avisos
    avisos_completa = checa_minimos(
        basica=[item] * 3 + [item_doaj_eissn],
        complementar=[item_fisico] * 5 + [item_doaj_ambos],
    )
    assert len(avisos_completa) == 0, f"não deveria ter avisos: {avisos_completa}"

    # 5. checa_minimos: bloco sem periódico cita o bloco específico
    avisos_sem_p_basica = checa_minimos(
        basica=[item] * 3,
        complementar=[item_fisico] * 5 + [item_doaj_eissn],
    )
    assert any("Básica: falta o periódico" in a for a in avisos_sem_p_basica), avisos_sem_p_basica
    assert not any("Complementar: falta o periódico" in a for a in avisos_sem_p_basica), avisos_sem_p_basica

    avisos_sem_p_compl = checa_minimos(
        basica=[item] * 3 + [item_doaj_eissn],
        complementar=[item_fisico] * 5,
    )
    assert any("Complementar: falta o periódico" in a for a in avisos_sem_p_compl), avisos_sem_p_compl
    assert not any("Básica: falta o periódico" in a for a in avisos_sem_p_compl), avisos_sem_p_compl

    # 6. checa_minimos: periódico sem acesso_aberto_doaj gera aviso de confirmação manual
    periodico_manual = {
        "titulo": "IEEE Transactions on Software Engineering",
        "issn": "0098-5589",
        "periodico": True,
        "acesso_aberto_doaj": False,
    }
    avisos_manual = checa_minimos(
        basica=[item] * 3 + [periodico_manual],
        complementar=[item_fisico] * 5 + [item_doaj_eissn],
    )
    assert any("Básica: periódico \"IEEE Transactions on Software Engineering\" sem confirmação" in a and "confirme manualmente" in a for a in avisos_manual), avisos_manual
    assert not any("Complementar" in a for a in avisos_manual), avisos_manual

    # 7. checa_minimos: 3 itens na Básica sendo 2 livros + 1 periódico -> avisa que a Básica tem 2 títulos (periódico não conta como livro)
    avisos_dois_livros = checa_minimos(
        basica=[item] * 2 + [item_doaj_eissn],
        complementar=[item_fisico] * 5 + [item_doaj_eissn],
    )
    assert any("Básica tem 2 título(s)" in a for a in avisos_dois_livros), avisos_dois_livros

    # 8. checa_minimos: complementar sem exemplar físico
    avisos_sem_fisico = checa_minimos(
        basica=[item] * 3 + [item_doaj_eissn],
        complementar=[item] * 5 + [item_doaj_eissn],
    )
    assert any("exemplar físico" in a for a in avisos_sem_fisico), avisos_sem_fisico

    # 9. checa_minimos: básica sem item virtual
    avisos_sem_virtual = checa_minimos(
        basica=[item_fisico] * 3 + [item_doaj_eissn],
        complementar=[item_fisico] * 5 + [item_doaj_eissn],
    )
    assert any("biblioteca virtual" in a for a in avisos_sem_virtual), avisos_sem_virtual

    # 10. Funções auxiliares de extração e compatibilidade do PPC
    ref_exemplo = "1. TANENBAUM, Andrew Stuart. **Organização estruturada de computadores**. 6. ed. São Paulo: Pearson, 2013."
    sob, ini_tit, tit_comp = extrai_autor_e_titulo(ref_exemplo)
    assert sob == "TANENBAUM"
    assert ini_tit == "Organização estruturada de"
    assert tit_comp == "Organização estruturada de computadores"
    assert titulo_compativel(tit_comp, "Organização estruturada de computadores / 2013")
    assert not titulo_compativel(tit_comp, "Engenharia de software / 2019")

    bloco_exemplo = "1. Ref A. **Titulo A**. 2020. 2. Ref B. **Titulo B**. 2021."
    refs_separadas = separa_referencias_ppc(bloco_exemplo)
    assert len(refs_separadas) == 2

    print(f"demo ok — classifica_registro, classifica_periodico e checa_minimos batem (incompleta: {len(avisos_incompleta)} avisos, completa: {len(avisos_completa)} avisos)")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
