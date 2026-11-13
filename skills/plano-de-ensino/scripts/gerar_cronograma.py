#!/usr/bin/env python3
"""Calcula o cronograma de um plano de ensino: distribui os encontros de aula
entre os RAs conforme o peso de cada um, busca feriados nacionais na BrasilAPI,
calcula a carga oficial de TDE (Trabalho Discente Efetivo) pela regra institucional
da PUCPR e insere as atividades de TDE com data ou no fechamento do bloco.

Só biblioteca padrão do Python — sem pip install, sem chamada de rede além da
BrasilAPI (com fallback se não houver internet).

Uso:
    python3 gerar_cronograma.py dados.json > cronograma.json

Cada linha de saída traz: indice (nº sequencial da sessão, None pra TDE sem
data fixa — mesmo padrão de linha administrativa sem número dos planos
reais), data (DD/MM ou DD/MM/AAAA conforme "formato_data" — ou o rótulo do
período, ex: "Semana de 04/08 a 08/08", se "granularidade" != "dia"),
data_iso (uso interno), ra, descricao, carga_horaria (número, uso interno) e
carga_horaria_fmt ("HH:MM", formato dos planos reais). O documento final usa
indice/data/ra/descricao/carga_horaria_fmt — "#" é a primeira coluna da
tabela de cronograma no template oficial ("Data" ou "Período", conforme a
granularidade).

Formato de dados.json:
{
  "data_inicio": "2026-08-05",
  "data_fim": "2026-12-05",
  "dias_semana": {"terca": 4},                # ou {"terca": 2, "quinta": 2}
  "campus": "ctb",                              # ctb, lon ou tol — aplica feriados locais e dias de TDE
                                               # do calendário institucional (references/calendario-2026.json)
  "recessos_manuais": ["2026-11-02"],          # pontos facultativos institucionais
  "formato_data": "dd_mm",                     # ou "dd_mm_aaaa" — opcional, default "dd_mm";
                                               # só relevante se granularidade == "dia"
  "feriados_como_linha": false,                 # opcional — true: feriado nacional ("Feriado") e
                                               # recesso manual ("Recesso Acadêmico") viram linha
                                               # visível no cronograma (RA "-", carga horária do
                                               # dia, não consome a meta de nenhum RA)
  "granularidade": "dia",                       # opcional — "dia" (default), "semana", "quinzena"
                                               # ou "mes": agrupa encontros consecutivos do mesmo
                                               # RA no mesmo período numa linha só (soma carga
                                               # horária, junta as descrições) — a % de cada RA
                                               # não muda, só a apresentação. Coluna "data" passa
                                               # a trazer o rótulo do período em vez da data.
  "datas_2a_chamada": [                          # opcional — datas previstas de avaliação de 2ª
    {"data": "2026-11-10", "descricao": "2ª Chamada"}   # chamada (Art. 29, Resolução 414/2024). Se a
  ],                                              # data cai num encontro existente, anota nele; senão
                                                 # vira linha própria (RA "-", mesmo padrão de feriado)
  "ras": [
    {"nome": "RA1", "percentual": 30, "temas": ["Tema A", "Tema B"],
     "tde": [
       {"horas": 4, "quantidade": 1},          # formato antigo (mantido por compatibilidade)
       {"horas": 2, "descricao": "Questionário Diagnóstico", "data": "2026-08-11",
        "integrado_com": "Outra Disciplina"}   # formato novo (descricao, data e integrado_com opcionais)
     ]},
    {"nome": "RA2", "percentual": 70, "temas": ["Tema C"], "tde": []}
  ]
}
"""
import json
from pathlib import Path
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import date, timedelta

DIAS_SEMANA_PT = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
            "agosto", "setembro", "outubro", "novembro", "dezembro"]


def formata_carga_horaria(horas):
    """4 -> '04:00' — formato usado nos planos de ensino reais (HH:MM)."""
    h = int(horas)
    m = round((horas - h) * 60)
    return f"{h:02d}:{m:02d}"


def normaliza_dia(nome):
    """'Terça', 'terça-feira', 'TERCA' -> 'terca'."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c)
    )
    sem_acento = sem_acento.lower().strip()
    for dia in DIAS_SEMANA_PT:
        if sem_acento.startswith(dia):
            return dia
    raise ValueError(f"dia da semana não reconhecido: {nome!r}")


def parse_data(s):
    if isinstance(s, date):
        return s
    return date.fromisoformat(s)


def calcula_tde_oficial(aulas_por_dia, ocorrencias):
    """Calcula CHTD, presencial e TDE (horas-aula e horas-relógio)
    pela fórmula institucional da PUCPR (Resolução CONSUN 249/2026 / calculadora TDE):
    - CHTD = (aulas por semana) * 20
    - presencial = soma(aulas naquele dia x ocorrências do dia no semestre)
    - TDE (hora-aula) = CHTD - presencial
    - TDE (hora-relógio) = TDE (hora-aula) * 0.75

    aulas_por_dia: lista de 6 posições (segunda a sábado), nº de aulas em cada dia.
    ocorrencias: lista de 6 posições (segunda a sábado), nº de vezes que o dia tem aula no semestre.
    Retorna {"chtd", "presencial", "tde_ha", "tde_hr"}; int com aulas inteiras, float com aula fracionária (ex.: 1,5 ha).
    """
    if len(aulas_por_dia) != 6 or len(ocorrencias) != 6:
        raise ValueError("aulas_por_dia e ocorrencias devem ter exatamente 6 posições (seg a sáb)")
    aulas_semana = sum(aulas_por_dia)
    chtd = aulas_semana * 20
    presencial = sum(a * o for a, o in zip(aulas_por_dia, ocorrencias))
    tde_ha = chtd - presencial
    tde_hr = float(tde_ha * 0.75)
    return {
        "chtd": chtd,
        "presencial": presencial,
        "tde_ha": tde_ha,
        "tde_hr": tde_hr,
    }


def dias_suspensos_do_campus(calendario, campus):
    """Set de date com aula suspensa (feriado, recesso, dia de TDE) no câmpus
    ('ctb', 'lon' ou 'tol'), segundo o calendário institucional."""
    campi_validos = sorted(set(c for ev in calendario.get("eventos", []) for c in ev.get("campus", [])))
    if campus not in campi_validos:
        raise ValueError(
            f"câmpus {campus!r} não encontrado nos eventos do calendário — siglas válidas: {', '.join(campi_validos)}"
        )
    suspensos = set()
    for ev in calendario.get("eventos", []):
        if ev.get("suspende_aula") and campus in ev.get("campus", []):
            cur = date.fromisoformat(ev["data"])
            fim = date.fromisoformat(ev["data_fim"]) if "data_fim" in ev else cur
            while cur <= fim:
                suspensos.add(cur)
                cur += timedelta(days=1)
    return suspensos


def conta_ocorrencias_dias(calendario, semestre, campus):
    """Conta ocorrências de cada dia da semana (seg a sáb, 6 posições)
    no semestre letivo para o câmpus especificado a partir do calendário institucional.
    - calendario: dict carregado do calendário (ex: calendario-2026.json)
    - semestre: '1' ou '2' (ou int 1 ou 2)
    - campus: 'ctb', 'lon' ou 'tol'
    Retorna lista de 6 inteiros [seg, ter, qua, qui, sex, sab].
    """
    semestre_str = str(semestre)
    sem = calendario["semestres"][semestre_str]
    d_ini = date.fromisoformat(sem["inicio_aulas"])
    d_fim = date.fromisoformat(sem["fim_aulas"])

    dias_suspensos = dias_suspensos_do_campus(calendario, campus)

    counts = [0] * 6
    cur = d_ini
    while cur <= d_fim:
        wd = cur.weekday()
        if wd < 6:
            if cur not in dias_suspensos:
                counts[wd] += 1
        cur += timedelta(days=1)
    return counts


def busca_feriados_nacionais(anos):
    """GET BrasilAPI (stdlib urllib, sem chave). Retorna set de 'YYYY-MM-DD' ou
    None se não conseguir buscar (sem internet, API fora do ar, etc) — quem
    chama decide o fallback (pedir a lista manual ao professor).

    User-Agent explícito é obrigatório: o WAF da BrasilAPI (Cloudflare)
    devolve 403 pro User-Agent padrão do urllib ("Python-urllib/3.x")."""
    feriados = set()
    for ano in sorted(anos):
        url = f"https://brasilapi.com.br/api/feriados/v1/{ano}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
            feriados.update(item["date"] for item in dados)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
            return None
    return feriados


def gera_encontros(data_inicio, data_fim, dias_semana, feriados_nacionais, recessos_manuais, feriados_como_linha=False):
    """dias_semana: dict {dia_normalizado: horas}. feriados_nacionais/recessos_manuais:
    sets de 'YYYY-MM-DD'. Com feriados_como_linha=True, datas de feriado/recesso que
    caem em dia de aula continuam no resultado, marcadas com "feriado"/"recesso": True
    — quem chama decide como renderizar (linha visível "Feriado"/"Recesso Acadêmico",
    sem consumir meta de RA)."""
    encontros = []
    d = data_inicio
    while d <= data_fim:
        dia_idx = d.weekday()  # segunda=0 ... domingo=6
        dia_nome = DIAS_SEMANA_PT[dia_idx]
        if dia_nome in dias_semana:
            iso = d.isoformat()
            if iso not in feriados_nacionais and iso not in recessos_manuais:
                encontros.append({"data": d, "horas": dias_semana[dia_nome]})
            elif feriados_como_linha:
                tag = "feriado" if iso in feriados_nacionais else "recesso"
                encontros.append({"data": d, "horas": dias_semana[dia_nome], tag: True})
        d += timedelta(days=1)
    return encontros


def _rotulo_periodo(data, granularidade):
    if granularidade == "semana":
        inicio = data - timedelta(days=data.weekday())
        fim = inicio + timedelta(days=6)
        return f"Semana de {inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
    if granularidade == "quinzena":
        quinzena = "1ª" if data.day <= 15 else "2ª"
        return f"{quinzena} quinzena de {MESES_PT[data.month - 1]}"
    if granularidade == "mes":
        return f"{MESES_PT[data.month - 1]} de {data.year}"
    raise ValueError(f"granularidade desconhecida: {granularidade!r}")


def agrupa_por_periodo(linhas, granularidade):
    """Junta encontros consecutivos do mesmo RA no mesmo período (semana/
    quinzena/mês) numa linha só — soma carga horária, concatena descrições.
    Linhas sem data fixa (TDE, 2ª chamada avulsa) nunca agrupam."""
    if granularidade == "dia":
        return linhas

    def fecha(bucket):
        itens = bucket["linhas"]
        if len(itens) == 1:
            l = dict(itens[0])
            l["data"] = bucket["label"]
            return l
        return {
            "indice": itens[0]["indice"],
            "data": bucket["label"],
            "data_iso": itens[0]["data_iso"],
            "ra": itens[0]["ra"],
            "descricao": "; ".join(dict.fromkeys(i["descricao"] for i in itens)),
            "carga_horaria": sum(i["carga_horaria"] for i in itens),
            "carga_horaria_fmt": formata_carga_horaria(sum(i["carga_horaria"] for i in itens)),
        }

    agrupadas = []
    bucket_atual = None
    for linha in linhas:
        if linha["data_iso"] is None:
            if bucket_atual:
                agrupadas.append(fecha(bucket_atual))
                bucket_atual = None
            agrupadas.append(linha)
            continue
        label = _rotulo_periodo(date.fromisoformat(linha["data_iso"]), granularidade)
        chave = (linha["ra"], label)
        if bucket_atual and bucket_atual["chave"] == chave:
            bucket_atual["linhas"].append(linha)
        else:
            if bucket_atual:
                agrupadas.append(fecha(bucket_atual))
            bucket_atual = {"chave": chave, "label": label, "linhas": [linha]}
    if bucket_atual:
        agrupadas.append(fecha(bucket_atual))
    return agrupadas


def insere_2a_chamada(linhas, datas_2a_chamada, fmt_strftime):
    """Cada item: {"data": "YYYY-MM-DD", "descricao": "2ª Chamada" (opcional),
    "carga_horaria": 0 (opcional, só usada se a data não cair num encontro
    existente)}. Se cair, anota o encontro; senão insere linha própria
    (RA "-", mesmo padrão de feriado/recesso) na posição cronológica certa."""
    for item in datas_2a_chamada:
        iso = item["data"]
        tag = item.get("descricao", "2ª Chamada")
        achou = False
        for linha in linhas:
            if linha["data_iso"] == iso and linha["ra"] != "-":
                linha["descricao"] += f" [{tag}]"
                achou = True
                break
        if achou:
            continue
        horas = item.get("carga_horaria", 0)
        nova = {
            "indice": 0,  # renumerado depois
            "data": date.fromisoformat(iso).strftime(fmt_strftime),
            "data_iso": iso,
            "ra": "-",
            "descricao": tag,
            "carga_horaria": horas,
            "carga_horaria_fmt": formata_carga_horaria(horas),
        }
        pos = next((i for i, l in enumerate(linhas) if l["data_iso"] is not None and l["data_iso"] > iso), len(linhas))
        linhas.insert(pos, nova)
    return linhas


def renumera_indices(linhas):
    idx = 1
    for linha in linhas:
        if linha["indice"] is not None:
            linha["indice"] = idx
            idx += 1
    return linhas


def gera_cronograma(data_inicio, data_fim, dias_semana, feriados_nacionais, recessos_manuais, ras,
                     formato_data="dd_mm", feriados_como_linha=False, granularidade="dia", datas_2a_chamada=None):
    """Retorna (linhas, avisos). linhas = [{data, ra, descricao, carga_horaria}]."""
    if not ras:
        raise ValueError("nenhum RA informado — defina ao menos um Resultado de Aprendizagem antes de gerar o cronograma")
    avisos = []
    fmt_strftime = "%d/%m/%Y" if formato_data == "dd_mm_aaaa" else "%d/%m"
    feriados_nacionais = set(feriados_nacionais)
    recessos_manuais = set(recessos_manuais)
    encontros = gera_encontros(data_inicio, data_fim, dias_semana, feriados_nacionais, recessos_manuais, feriados_como_linha)
    if not encontros:
        raise ValueError("nenhum encontro gerado — confira o range de datas e os dias da semana")

    carga_total = sum(e["horas"] for e in encontros if not e.get("feriado") and not e.get("recesso"))
    soma_pct = sum(ra["percentual"] for ra in ras)
    if abs(soma_pct - 100) > 0.01:
        avisos.append(f"percentuais dos RAs somam {soma_pct}%, não 100%")

    tde_total = sum(t["horas"] * t.get("quantidade", 1) for ra in ras for t in ra.get("tde", []))
    for ra in ras:
        ra["_meta_total"] = (carga_total + tde_total) * ra["percentual"] / 100
        ra_tdes = []
        for t in ra.get("tde", []):
            qtd = t.get("quantidade", 1)
            for _ in range(qtd):
                ra_tdes.append({
                    "horas": t["horas"],
                    "descricao": t.get("descricao"),
                    "data": t.get("data"),
                    "integrado_com": t.get("integrado_com"),
                    "ra": ra["nome"],
                })
        ra["_tdes_normalizados"] = ra_tdes
        ra["_tde_horas"] = sum(t["horas"] for t in ra_tdes)
        ra["_meta_aula"] = max(0.0, ra["_meta_total"] - ra["_tde_horas"])
        if ra["_tde_horas"] > ra["_meta_total"]:
            avisos.append(f"{ra['nome']}: carga de TDE ({ra['_tde_horas']}h) excede a carga total do RA ({ra['_meta_total']}h)")
        ra["_temas_restantes"] = list(ra.get("temas", []))
        ra["_horas_aula_acumuladas"] = 0.0
        ra["_datas_aulas"] = []

    # Cálculo do TDE oficial da disciplina (aulas/semana * 20 - carga_total presencial)
    if dias_semana:
        aulas_semana = sum(dias_semana.values())
        tde_oficial = aulas_semana * 20 - carga_total
        tde_cadastrado = sum(ra["_tde_horas"] for ra in ras)
        if tde_cadastrado != tde_oficial:
            avisos.append(f"soma de TDE cadastrada ({tde_cadastrado}h) difere do cálculo oficial ({tde_oficial}h)")
    else:
        avisos.append("não foi possível calcular o TDE oficial: dias_semana ausente ou vazio")

    linhas = []
    indice = 1
    ra_idx = 0
    for encontro in encontros:
        if encontro.get("feriado") or encontro.get("recesso"):
            linhas.append({
                "indice": indice,
                "data": encontro["data"].strftime(fmt_strftime),
                "data_iso": encontro["data"].isoformat(),
                "ra": "-",
                "descricao": "Feriado" if encontro.get("feriado") else "Recesso Acadêmico",
                "carga_horaria": encontro["horas"],
                "carga_horaria_fmt": formata_carga_horaria(encontro["horas"]),
            })
            indice += 1
            continue

        while (
            ra_idx < len(ras) - 1
            and ras[ra_idx]["_horas_aula_acumuladas"] >= ras[ra_idx]["_meta_aula"]
        ):
            ra_idx += 1
        ra = ras[ra_idx]
        if ra["_temas_restantes"]:
            descricao = ra["_temas_restantes"].pop(0)
        else:
            descricao = "[definir conteúdo]"
            avisos.append(f"{ra['nome']}: acabaram os temas antes das aulas (encontro de {encontro['data'].isoformat()} sem tema)")
        linhas.append({
            "indice": indice,  # numeração sequencial da linha, como nos planos reais (coluna "#")
            "data": encontro["data"].strftime(fmt_strftime),  # DD/MM (padrão) ou DD/MM/AAAA
            "data_iso": encontro["data"].isoformat(),
            "ra": ra["nome"],
            "descricao": descricao,
            "carga_horaria": encontro["horas"],
            "carga_horaria_fmt": formata_carga_horaria(encontro["horas"]),
        })
        indice += 1
        ra["_horas_aula_acumuladas"] += encontro["horas"]
        ra["_datas_aulas"].append(encontro["data"])

        # RA trocou de bloco (ou é o último encontro do RA atual) -> insere TDEs pendentes sem data
        proximo_ra_vai_comecar = ra_idx < len(ras) - 1 and ra["_horas_aula_acumuladas"] >= ra["_meta_aula"]
        ultimo_encontro_geral = encontro is encontros[-1]
        if (proximo_ra_vai_comecar or ultimo_encontro_geral) and not ra.get("_tde_sem_data_inserido"):
            for tde in ra["_tdes_normalizados"]:
                if not tde.get("data"):
                    linhas.append({
                        "indice": None,  # sem data fixa -> sem número de sessão, como as linhas administrativas dos planos reais
                        "data": "[professor define a data]",
                        "data_iso": None,
                        "ra": ra["nome"],
                        "descricao": "",
                        "carga_horaria": tde["horas"],
                        "carga_horaria_fmt": formata_carga_horaria(tde["horas"]),
                        "_tde_info": tde,
                    })
            ra["_tde_sem_data_inserido"] = True

    # Para RAs que não tiveram encontros presenciais mas têm TDE sem data cadastrado
    for ra in ras:
        if not ra.get("_tde_sem_data_inserido"):
            for tde in ra["_tdes_normalizados"]:
                if not tde.get("data"):
                    linhas.append({
                        "indice": None,
                        "data": "[professor define a data]",
                        "data_iso": None,
                        "ra": ra["nome"],
                        "descricao": "",
                        "carga_horaria": tde["horas"],
                        "carga_horaria_fmt": formata_carga_horaria(tde["horas"]),
                        "_tde_info": tde,
                    })
            ra["_tde_sem_data_inserido"] = True

    # Processa TDEs com data
    for ra in ras:
        ra_datas = ra.get("_datas_aulas", [])
        ra_inicio = min(ra_datas) if ra_datas else data_inicio
        ra_fim = max(ra_datas) if ra_datas else data_fim

        for tde in ra["_tdes_normalizados"]:
            if not tde.get("data"):
                continue
            data_str = tde["data"]
            d_tde = parse_data(data_str)

            # Validações de data fora do intervalo do semestre ou do bloco do RA
            if d_tde < data_inicio or d_tde > data_fim:
                avisos.append(
                    f"{ra['nome']}: data do TDE ({data_str}) fora do intervalo do semestre "
                    f"({data_inicio.isoformat()} a {data_fim.isoformat()})"
                )
            elif ra_datas and (d_tde < ra_inicio or d_tde > ra_fim):
                avisos.append(
                    f"{ra['nome']}: data do TDE ({data_str}) fora do intervalo do bloco do RA "
                    f"({ra_inicio.isoformat()} a {ra_fim.isoformat()})"
                )

            # Verifica se já existe linha de feriado/recesso gerada para aquela data
            linha_feriado = None
            for l in linhas:
                if (
                    l["data_iso"] == data_str
                    and l["ra"] == "-"
                    and l["descricao"] in ("Feriado", "Recesso Acadêmico")
                    and "_combinado_feriado" not in l
                ):
                    linha_feriado = l
                    break

            if linha_feriado is not None:
                linha_feriado["ra"] = ra["nome"]
                linha_feriado["carga_horaria"] = tde["horas"]
                linha_feriado["carga_horaria_fmt"] = formata_carga_horaria(tde["horas"])
                linha_feriado["_combinado_feriado"] = True
                linha_feriado["_feriado_desc"] = linha_feriado["descricao"]
                linha_feriado["_tde_info"] = tde
            else:
                nova_linha = {
                    "indice": 0,  # renumerado depois
                    "data": d_tde.strftime(fmt_strftime),
                    "data_iso": data_str,
                    "ra": ra["nome"],
                    "descricao": "",
                    "carga_horaria": tde["horas"],
                    "carga_horaria_fmt": formata_carga_horaria(tde["horas"]),
                    "_tde_info": tde,
                }

                def _pos_insercao(linha):
                    if linha["data_iso"] is not None and linha["data_iso"] > data_str:
                        return True
                    if linha["data_iso"] is None and linha.get("ra") == ra["nome"]:
                        return True
                    return False

                pos = next((i for i, l in enumerate(linhas) if _pos_insercao(l)), len(linhas))
                linhas.insert(pos, nova_linha)

    # Numeração sequencial dos TDEs no plano inteiro, na ordem em que aparecem
    tde_idx = 1
    for linha in linhas:
        if "_tde_info" in linha:
            info = linha.pop("_tde_info")
            desc = info.get("descricao")
            integ = info.get("integrado_com")
            if desc:
                tde_str = f"TDE {tde_idx:02d} \u2013 {desc}"
            else:
                tde_str = "TDE"
            if integ:
                tde_str += f" (integrado com {integ})"

            if linha.get("_combinado_feriado"):
                linha.pop("_combinado_feriado")
                feriado_desc = linha.pop("_feriado_desc", "Feriado")
                linha["descricao"] = f"{feriado_desc} ({tde_str})"
            else:
                linha["descricao"] = tde_str
            tde_idx += 1

    for ra in ras:
        if ra["_temas_restantes"]:
            avisos.append(
                f"{ra['nome']}: sobraram {len(ra['_temas_restantes'])} tema(s) sem aula "
                f"pra encaixar ({', '.join(ra['_temas_restantes'])}) — cronograma tem menos "
                f"encontros do que temas cadastrados pra esse RA"
            )

    if datas_2a_chamada:
        dentro = [i for i in datas_2a_chamada if data_inicio.isoformat() <= i["data"] <= data_fim.isoformat()]
        for i in datas_2a_chamada:
            if i not in dentro:
                avisos.append(
                    f"2ª chamada em {i['data']} fica fora do semestre ({data_inicio.isoformat()} a {data_fim.isoformat()}) "
                    f"e não entrou no cronograma — descreva essa data no texto de avaliação"
                )
        linhas = insere_2a_chamada(linhas, dentro, fmt_strftime)
    linhas = agrupa_por_periodo(linhas, granularidade)
    linhas = renumera_indices(linhas)

    return linhas, avisos


def carrega_dados(caminho):
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    dados["data_inicio"] = parse_data(dados["data_inicio"])
    dados["data_fim"] = parse_data(dados["data_fim"])
    dados["dias_semana"] = {normaliza_dia(k): v for k, v in dados["dias_semana"].items()}
    dados.setdefault("recessos_manuais", [])
    dados.setdefault("formato_data", "dd_mm")
    dados.setdefault("feriados_como_linha", False)
    dados.setdefault("granularidade", "dia")
    dados.setdefault("datas_2a_chamada", [])
    for ra in dados["ras"]:
        ra.setdefault("tde", [])
        ra.setdefault("temas", [])
    return dados


def main():
    if len(sys.argv) != 2:
        print("uso: python3 gerar_cronograma.py dados.json", file=sys.stderr)
        sys.exit(1)

    dados = carrega_dados(sys.argv[1])
    anos = {dados["data_inicio"].year, dados["data_fim"].year}
    feriados = busca_feriados_nacionais(anos)
    aviso_feriados = None
    if feriados is None:
        aviso_feriados = "não consegui buscar feriados nacionais na BrasilAPI (sem internet ou API fora do ar) — confirme com o professor se há feriados no período e passe em recessos_manuais"
        feriados = set()

    recessos = list(dados["recessos_manuais"])
    avisos_cal = []
    cal_path = Path(__file__).resolve().parent.parent / "references" / "calendario-2026.json"
    cal = json.loads(cal_path.read_text(encoding="utf-8"))
    campus = dados.get("campus")
    if not campus:
        avisos_cal.append("câmpus não informado — feriados locais e dias de TDE do calendário institucional NÃO foram aplicados; informe campus (ctb, lon ou tol)")
    elif {dados["data_inicio"].year, dados["data_fim"].year} != {cal["ano"]}:
        avisos_cal.append(f"o calendário institucional só cobre {cal['ano']} — confira feriados locais e passe em recessos_manuais")
    else:
        recessos += [d.isoformat() for d in dias_suspensos_do_campus(cal, campus)]

    linhas, avisos = gera_cronograma(
        dados["data_inicio"], dados["data_fim"], dados["dias_semana"],
        feriados, recessos, dados["ras"],
        formato_data=dados["formato_data"], feriados_como_linha=dados["feriados_como_linha"],
        granularidade=dados["granularidade"], datas_2a_chamada=dados["datas_2a_chamada"],
    )
    avisos = avisos_cal + avisos
    if aviso_feriados:
        avisos.insert(0, aviso_feriados)

    print(json.dumps({"cronograma": linhas, "avisos": avisos}, ensure_ascii=False, indent=2))


def demo():
    """Auto-checagem: roda cenários conhecidos e valida as invariantes do
    algoritmo, paridade com a calculadora e testes C1 a C9.
    python3 gerar_cronograma.py --demo"""

    # --- F1 (regressão): calendário do câmpus tira feriado local e dia de TDE ---
    cal_f1 = json.loads((Path(__file__).resolve().parent.parent / "references" / "calendario-2026.json").read_text(encoding="utf-8"))
    ctb = dias_suspensos_do_campus(cal_f1, "ctb")
    assert date(2026, 9, 8) in ctb and date(2026, 10, 17) in ctb and date(2026, 10, 19) in ctb
    assert date(2026, 9, 8) not in dias_suspensos_do_campus(cal_f1, "lon")
    l1, _ = gera_cronograma(
        date(2026, 9, 1), date(2026, 9, 15), {"terca": 4}, set(), [d.isoformat() for d in ctb],
        [{"nome": "RA1", "percentual": 100, "temas": ["a", "b", "c"]}],
    )
    assert "08/09" not in [x["data"] for x in l1], l1

    # --- F6 (regressão): 2ª chamada fora do semestre vira aviso, sem linha 00:00 ---
    l6, av6 = gera_cronograma(
        date(2026, 8, 3), date(2026, 8, 31), {"segunda": 4}, set(), [],
        [{"nome": "RA1", "percentual": 100, "temas": ["a", "b", "c", "d"]}],
        datas_2a_chamada=[{"data": "2026-12-20"}],
    )
    assert not any(x["carga_horaria"] == 0 and x["ra"] == "-" for x in l6), l6
    assert any("fora do semestre" in a for a in av6), av6

    # --- F7 (regressão): aula fracionária não é truncada ---
    r = calcula_tde_oficial([1.5, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0])
    assert r["presencial"] == 1.5 and r["tde_ha"] == 28.5 and r["chtd"] == 30, r

    # --- F2 (regressão): lista de RAs vazia vira erro claro, não IndexError ---
    try:
        gera_cronograma(date(2026, 8, 3), date(2026, 8, 31), {"segunda": 4}, set(), [], [])
        raise AssertionError("ras vazio deveria levantar ValueError")
    except ValueError as e:
        assert "nenhum RA" in str(e), e

    # --- C1 (regressão): valores esperados literais pré-mudança ---
    esperado_demo_literal = [
        {"indice": 1, "data": "04/08", "data_iso": "2026-08-04", "ra": "RA1", "descricao": "Introdução", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 2, "data": "11/08", "data_iso": "2026-08-11", "ra": "RA1", "descricao": "Fundamentos", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 3, "data": "18/08", "data_iso": "2026-08-18", "ra": "RA1", "descricao": "Prática 1", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 4, "data": "25/08", "data_iso": "2026-08-25", "ra": "RA1", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 5, "data": "01/09", "data_iso": "2026-09-01", "ra": "RA1", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": None, "data": "[professor define a data]", "data_iso": None, "ra": "RA1", "descricao": "TDE", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 6, "data": "15/09", "data_iso": "2026-09-15", "ra": "RA2", "descricao": "Avançado 1", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 7, "data": "22/09", "data_iso": "2026-09-22", "ra": "RA2", "descricao": "Avançado 2", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 8, "data": "29/09", "data_iso": "2026-09-29", "ra": "RA2", "descricao": "Projeto", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 9, "data": "06/10", "data_iso": "2026-10-06", "ra": "RA2", "descricao": "Revisão", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 10, "data": "13/10", "data_iso": "2026-10-13", "ra": "RA2", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 11, "data": "20/10", "data_iso": "2026-10-20", "ra": "RA2", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 12, "data": "27/10", "data_iso": "2026-10-27", "ra": "RA2", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
    ]

    esperado_antigo_literal = [
        {"indice": 1, "data": "04/08", "data_iso": "2026-08-04", "ra": "RA1", "descricao": "Introdução", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 2, "data": "11/08", "data_iso": "2026-08-11", "ra": "RA1", "descricao": "Fundamentos", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 3, "data": "18/08", "data_iso": "2026-08-18", "ra": "RA1", "descricao": "Prática 1", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 4, "data": "25/08", "data_iso": "2026-08-25", "ra": "RA1", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 5, "data": "01/09", "data_iso": "2026-09-01", "ra": "RA1", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": None, "data": "[professor define a data]", "data_iso": None, "ra": "RA1", "descricao": "TDE", "carga_horaria": 2, "carga_horaria_fmt": "02:00"},
        {"indice": None, "data": "[professor define a data]", "data_iso": None, "ra": "RA1", "descricao": "TDE", "carga_horaria": 2, "carga_horaria_fmt": "02:00"},
        {"indice": 6, "data": "15/09", "data_iso": "2026-09-15", "ra": "RA2", "descricao": "Avançado 1", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 7, "data": "22/09", "data_iso": "2026-09-22", "ra": "RA2", "descricao": "Avançado 2", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 8, "data": "29/09", "data_iso": "2026-09-29", "ra": "RA2", "descricao": "Projeto", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 9, "data": "06/10", "data_iso": "2026-10-06", "ra": "RA2", "descricao": "Revisão", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 10, "data": "13/10", "data_iso": "2026-10-13", "ra": "RA2", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 11, "data": "20/10", "data_iso": "2026-10-20", "ra": "RA2", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
        {"indice": 12, "data": "27/10", "data_iso": "2026-10-27", "ra": "RA2", "descricao": "[definir conteúdo]", "carga_horaria": 4, "carga_horaria_fmt": "04:00"},
    ]

    ras = [
        {"nome": "RA1", "percentual": 40, "temas": ["Introdução", "Fundamentos", "Prática 1"], "tde": [{"horas": 4, "quantidade": 1}]},
        {"nome": "RA2", "percentual": 60, "temas": ["Avançado 1", "Avançado 2", "Projeto", "Revisão"], "tde": []},
    ]
    linhas, avisos = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 10, 27),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=["2026-09-08"],
        ras=ras,
    )
    assert linhas == esperado_demo_literal, "C1 regressão: saída do demo difere do valor esperado literal pré-mudança"

    ras_antigo = [
        {"nome": "RA1", "percentual": 40, "temas": ["Introdução", "Fundamentos", "Prática 1"], "tde": [{"horas": 2, "quantidade": 2}]},
        {"nome": "RA2", "percentual": 60, "temas": ["Avançado 1", "Avançado 2", "Projeto", "Revisão"], "tde": []},
    ]
    linhas_antigo, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 10, 27),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=["2026-09-08"],
        ras=ras_antigo,
    )
    assert linhas_antigo == esperado_antigo_literal, "C1 regressão: saída com formato antigo (quantidade: 2) difere do valor literal"

    datas_iso = [l["data_iso"] for l in linhas if l["data_iso"] is not None]
    datas_br = [l["data"] for l in linhas if l["data_iso"] is not None]
    assert datas_iso == sorted(datas_iso), "datas fora de ordem"
    assert "2026-09-08" not in datas_iso, "recesso manual não foi excluído"
    for d in datas_iso:
        assert date.fromisoformat(d).weekday() == 1, f"encontro fora do dia da semana pedido: {d}"
        assert date(2026, 8, 4) <= date.fromisoformat(d) <= date(2026, 10, 27), f"data fora do range: {d}"
    for d_iso, d_br in zip(datas_iso, datas_br):
        assert d_br == date.fromisoformat(d_iso).strftime("%d/%m"), f"data BR não bate com data_iso: {d_br} vs {d_iso}"
        assert "/" in d_br and len(d_br) == 5, f"data não está no formato DD/MM: {d_br!r}"

    for ra_nome, ra_pct in [("RA1", 40), ("RA2", 60)]:
        horas_ra = sum(l["carga_horaria"] for l in linhas if l["ra"] == ra_nome)
        carga_total = sum(4 for _ in datas_iso)  # 4h por encontro nesse cenário fixo
        tde_total = 4  # único TDE de 4h do cenário (RA1); horas_ra inclui a linha de TDE
        meta = (carga_total + tde_total) * ra_pct / 100
        assert abs(horas_ra - meta) <= 4, f"{ra_nome}: horas geradas ({horas_ra}) longe da meta ({meta})"

    tde_linhas = [l for l in linhas if l["descricao"] == "TDE"]
    assert len(tde_linhas) == 1 and tde_linhas[0]["ra"] == "RA1" and tde_linhas[0]["data"] == "[professor define a data]"
    assert tde_linhas[0]["indice"] is None, "TDE sem data fixa deveria ficar sem número de sessão"
    assert tde_linhas[0]["carga_horaria_fmt"] == "04:00", f"formato HH:MM incorreto: {tde_linhas[0]['carga_horaria_fmt']!r}"

    indices = [l["indice"] for l in linhas if l["indice"] is not None]
    assert indices == list(range(1, len(indices) + 1)), f"índices não são sequenciais 1..N: {indices}"

    # --- Issue #32 (regressão): percentual do RA incide sobre presencial + TDE total ---
    # 13 segundas, 4h cada = 52h presenciais; TDE 8+8+8+4 = 28h; total 80h.
    ras_32 = [
        {"nome": "RA1", "percentual": 25, "temas": [], "tde": [{"horas": 8, "quantidade": 1}]},
        {"nome": "RA2", "percentual": 30, "temas": [], "tde": [{"horas": 8, "quantidade": 1}]},
        {"nome": "RA3", "percentual": 20, "temas": [], "tde": [{"horas": 8, "quantidade": 1}]},
        {"nome": "RA4", "percentual": 25, "temas": [], "tde": [{"horas": 4, "quantidade": 1}]},
    ]
    linhas_32, avisos_32 = gera_cronograma(
        data_inicio=date(2026, 8, 3),
        data_fim=date(2026, 10, 26),
        dias_semana={"segunda": 4},
        feriados_nacionais=[],
        recessos_manuais=[],
        ras=ras_32,
    )
    aulas_32 = {r: sum(1 for l in linhas_32 if l["ra"] == r and l["indice"] is not None) for r in ["RA1", "RA2", "RA3", "RA4"]}
    assert aulas_32 == {"RA1": 3, "RA2": 4, "RA3": 2, "RA4": 4}, f"#32: aulas por RA erradas: {aulas_32}"
    assert not any("excede" in a for a in avisos_32), f"#32: aviso de TDE indevido: {avisos_32}"
    assert not any("difere do cálculo oficial" in a for a in avisos_32), f"#32: TDE oficial deveria bater: {avisos_32}"

    # feriados_como_linha=True
    linhas_fer, avisos_fer = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 18),
        dias_semana={"terca": 4},
        feriados_nacionais={"2026-08-11"},
        recessos_manuais=[],
        ras=[{"nome": "RA1", "percentual": 100, "temas": ["A", "B"], "tde": []}],
        feriados_como_linha=True,
        formato_data="dd_mm_aaaa",
    )
    feriado_linhas = [l for l in linhas_fer if l["descricao"] == "Feriado"]
    assert len(feriado_linhas) == 1, f"esperava 1 linha de feriado, veio {len(feriado_linhas)}"
    assert feriado_linhas[0]["ra"] == "-" and feriado_linhas[0]["indice"] is not None
    assert feriado_linhas[0]["data"] == "11/08/2026", f"formato_data com ano não aplicado: {feriado_linhas[0]['data']!r}"
    horas_ra1_fer = sum(l["carga_horaria"] for l in linhas_fer if l["ra"] == "RA1")
    assert horas_ra1_fer == 8, f"feriado não deveria contar na meta do RA: {horas_ra1_fer}h"
    datas_normais = [l for l in linhas_fer if l["ra"] == "RA1"]
    assert all("/" in l["data"] and len(l["data"]) == 10 for l in datas_normais), "formato_data dd_mm_aaaa não aplicado às linhas normais"

    # granularidade="semana"
    linhas_semana, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 13),
        dias_semana={"terca": 4, "quinta": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=[{"nome": "RA1", "percentual": 100, "temas": ["Tema A", "Tema B", "Tema C", "Tema D"], "tde": []}],
        granularidade="semana",
    )
    assert len(linhas_semana) == 2, f"esperava 2 linhas (1 por semana), veio {len(linhas_semana)}"
    assert linhas_semana[0]["carga_horaria"] == 8 and linhas_semana[1]["carga_horaria"] == 8, "carga horária não somada no agrupamento"
    assert linhas_semana[0]["descricao"] == "Tema A; Tema B", f"descrição não concatenada: {linhas_semana[0]['descricao']!r}"
    assert linhas_semana[1]["descricao"] == "Tema C; Tema D"
    assert "Semana de" in linhas_semana[0]["data"], f"rótulo de período ausente: {linhas_semana[0]['data']!r}"
    assert [l["indice"] for l in linhas_semana] == [1, 2], "índices não renumerados após agrupamento"

    # datas_2a_chamada
    linhas_2a, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 25),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=[{"nome": "RA1", "percentual": 100, "temas": ["A", "B", "C", "D"], "tde": []}],
        datas_2a_chamada=[{"data": "2026-08-11"}, {"data": "2026-08-20", "descricao": "2ª Chamada Especial"}],
    )
    assert len(linhas_2a) == 5, f"esperava 5 linhas (4 encontros + 1 avulsa), veio {len(linhas_2a)}"
    linha_anotada = next(l for l in linhas_2a if l["data_iso"] == "2026-08-11")
    assert linha_anotada["descricao"].endswith(" [2ª Chamada]"), f"anotação de 2ª chamada ausente: {linha_anotada['descricao']!r}"
    linha_avulsa = next(l for l in linhas_2a if l["data_iso"] == "2026-08-20")
    assert linha_avulsa["ra"] == "-" and linha_avulsa["descricao"] == "2ª Chamada Especial"
    datas_ordem = [l["data_iso"] for l in linhas_2a]
    assert datas_ordem == sorted(datas_ordem), "linha de 2ª chamada avulsa não ficou na posição cronológica certa"
    assert [l["indice"] for l in linhas_2a] == list(range(1, 6)), "índices não renumerados após inserir 2ª chamada"

    # tema sobrando sem aula pra encaixar
    linhas_sobra, avisos_sobra = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 11),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=[{"nome": "RA1", "percentual": 100, "temas": ["A", "B", "C"], "tde": []}],
    )
    assert len(linhas_sobra) == 2, f"esperava 2 aulas (2 terças no range), veio {len(linhas_sobra)}"
    assert any("sobraram 1 tema" in a and "RA1" in a and "C" in a for a in avisos_sobra), f"aviso de tema sobrando ausente: {avisos_sobra}"

    # --- C2: cálculo oficial de TDE ---
    res_c2 = calcula_tde_oficial([2, 0, 2, 0, 0, 0], [13, 15, 17, 17, 16, 15])
    assert res_c2 == {"chtd": 80, "presencial": 60, "tde_ha": 20, "tde_hr": 15.0}, f"C2 falhou: {res_c2}"

    # --- C3: cálculo oficial com 4 aulas na terça ---
    res_c3 = calcula_tde_oficial([0, 4, 0, 0, 0, 0], [13, 15, 17, 17, 16, 15])
    assert res_c3["chtd"] == 80 and res_c3["presencial"] == 60 and res_c3["tde_ha"] == 20, f"C3 falhou: {res_c3}"
    assert res_c3["tde_hr"] == 15.0

    # --- C4 (paridade com a calculadora, sem rede) ---
    base_dir = Path(__file__).resolve().parent
    operacao_js_path = base_dir.parent / "references" / "calculadora-tde" / "operacao.js"
    cal_json_path = base_dir.parent / "references" / "calendario-2026.json"
    assert cal_json_path.exists(), f"arquivo calendario-2026.json não encontrado em {cal_json_path}"

    with open(cal_json_path, encoding="utf-8") as f:
        cal_data = json.load(f)

    # operacao.js (cópia da calculadora oficial) só existe no repo de desenvolvimento;
    # na distribuição pública o teste de paridade é pulado.
    if operacao_js_path.exists():
        js_text = operacao_js_path.read_text(encoding="utf-8")
        for campus in ["ctb", "lon", "tol"]:
            m = re.search(rf"const\s+{campus}_2_v\s*=\s*\[([0-9,\s]+)\];", js_text)
            assert m, f"C4: regex não encontrou {campus}_2_v em operacao.js"
            tabela_esperada = [int(x.strip()) for x in m.group(1).split(",")]
            contagem_derivada = conta_ocorrencias_dias(cal_data, "2", campus)
            assert contagem_derivada == tabela_esperada, (
                f"C4: paridade falhou para {campus}: contagem={contagem_derivada} != tabela={tabela_esperada}"
            )

    # Validação de câmpus inválido (deve levantar ValueError citando as siglas válidas)
    try:
        conta_ocorrencias_dias(cal_data, 2, "curitiba")
        assert False, "esperava ValueError para câmpus 'curitiba'"
    except ValueError as e:
        assert "ctb, lon, tol" in str(e), f"mensagem de erro deve citar as siglas válidas: {e}"

    # --- C5: item com data de aula no meio do bloco aparece entre as aulas ---
    ras_c5 = [{
        "nome": "RA1",
        "percentual": 100,
        "temas": ["Tema 1", "Tema 2", "Tema 3"],
        "tde": [{"horas": 2, "descricao": "Questionário Diagnóstico", "data": "2026-08-11"}]
    }]
    linhas_c5, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 25),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=ras_c5,
    )
    tde_c5 = [l for l in linhas_c5 if "Questionário Diagnóstico" in l["descricao"]]
    assert len(tde_c5) == 1, f"C5: esperava 1 linha de TDE, encontrou {len(tde_c5)}"
    assert tde_c5[0]["descricao"] == "TDE 01 – Questionário Diagnóstico", f"C5 descrição incorreta: {tde_c5[0]['descricao']}"
    assert tde_c5[0]["data"] == "11/08"
    assert tde_c5[0]["indice"] is not None
    # Verifica que aparece entre as aulas em ordem cronológica
    idx_tde = linhas_c5.index(tde_c5[0])
    datas_todas_c5 = [l["data_iso"] for l in linhas_c5 if l["data_iso"] is not None]
    assert datas_todas_c5 == sorted(datas_todas_c5), "C5: datas fora de ordem cronológica"
    assert any(l["data_iso"] == "2026-08-04" for l in linhas_c5[:idx_tde]), "C5: aula anterior não precede o TDE"
    assert any(l["data_iso"] == "2026-08-18" for l in linhas_c5[idx_tde:]), "C5: aula posterior não sucede o TDE"

    # --- C6: dois TDEs com data e um sem: numeração 01, 02, 03 na ordem de aparição; sem data no fim ---
    ras_c6 = [{
        "nome": "RA1",
        "percentual": 100,
        "temas": ["Tema 1", "Tema 2", "Tema 3"],
        "tde": [
            {"horas": 2, "descricao": "Quiz 1", "data": "2026-08-04"},
            {"horas": 2, "descricao": "Quiz 2", "data": "2026-08-11"},
            {"horas": 2, "descricao": "Quiz 3"},  # sem data
        ]
    }]
    linhas_c6, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 25),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=ras_c6,
    )
    tdes_c6 = [l for l in linhas_c6 if "Quiz" in l["descricao"]]
    assert len(tdes_c6) == 3, f"C6: esperava 3 TDEs, encontrou {len(tdes_c6)}"
    assert tdes_c6[0]["descricao"] == "TDE 01 – Quiz 1" and tdes_c6[0]["data"] == "04/08"
    assert tdes_c6[1]["descricao"] == "TDE 02 – Quiz 2" and tdes_c6[1]["data"] == "11/08"
    assert tdes_c6[2]["descricao"] == "TDE 03 – Quiz 3" and tdes_c6[2]["data"] == "[professor define a data]"
    assert tdes_c6[2]["indice"] is None, "C6: TDE sem data deve ter indice None"
    # O sem data fica no fim do bloco do RA (última linha do bloco do RA1)
    assert linhas_c6[-1] is tdes_c6[2], "C6: TDE sem data não ficou no fechamento do bloco"

    # --- C7: TDE com data em feriado com feriados_como_linha ligado ---
    ras_c7 = [{
        "nome": "RA1",
        "percentual": 100,
        "temas": ["Tema 1", "Tema 2"],
        "tde": [{"horas": 2, "descricao": "Github", "data": "2026-08-11"}]
    }]
    linhas_c7, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 18),
        dias_semana={"terca": 4},
        feriados_nacionais={"2026-08-11"},
        recessos_manuais=[],
        ras=ras_c7,
        feriados_como_linha=True,
    )
    linhas_fer_c7 = [l for l in linhas_c7 if l["data_iso"] == "2026-08-11"]
    assert len(linhas_fer_c7) == 1, f"C7: esperava exatamente 1 linha combinada no feriado, encontrou {len(linhas_fer_c7)}"
    assert linhas_fer_c7[0]["descricao"] == "Feriado (TDE 01 – Github)", f"C7: formato combinado incorreto: {linhas_fer_c7[0]['descricao']}"
    assert linhas_fer_c7[0]["carga_horaria"] == 2 and linhas_fer_c7[0]["carga_horaria_fmt"] == "02:00"
    assert linhas_fer_c7[0]["ra"] == "RA1", f"C7: RA do TDE esperado RA1, veio {linhas_fer_c7[0]['ra']}"

    # --- C8: soma de TDE cadastrada vs cálculo oficial ---
    # Cenário com diferença: dias_semana=4h (CHTD=80), 4 terças sem feriado (presencial=16h), tde_oficial=64h.
    # Cadastrado = 4h -> difere
    ras_c8_dif = [{"nome": "RA1", "percentual": 100, "temas": ["A"], "tde": [{"horas": 4}]}]
    _, avisos_c8_dif = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 25),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=ras_c8_dif,
    )
    aviso_tde_dif = [a for a in avisos_c8_dif if "difere do cálculo oficial" in a]
    assert len(aviso_tde_dif) == 1, f"C8: esperava 1 aviso de diferença de TDE, encontrou {aviso_tde_dif}"
    assert "4h" in aviso_tde_dif[0] and "64h" in aviso_tde_dif[0], f"C8: aviso deve conter os dois números: {aviso_tde_dif[0]}"

    # Cenário sem diferença: Cadastrado = 64h -> igual, não gera aviso
    ras_c8_eq = [{"nome": "RA1", "percentual": 100, "temas": ["A"], "tde": [{"horas": 64}]}]
    _, avisos_c8_eq = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 25),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=ras_c8_eq,
    )
    assert not any("difere do cálculo oficial" in a for a in avisos_c8_eq), "C8: não deveria gerar aviso quando TDE é igual"

    # --- C9: integrado_com aparece na descrição ---
    ras_c9 = [{
        "nome": "RA1",
        "percentual": 100,
        "temas": ["Tema 1"],
        "tde": [{"horas": 2, "descricao": "Projeto Integrado", "integrado_com": "Cálculo I"}]
    }]
    linhas_c9, _ = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 11),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=ras_c9,
    )
    tde_c9 = next(l for l in linhas_c9 if "Projeto Integrado" in l["descricao"])
    assert tde_c9["descricao"] == "TDE 01 – Projeto Integrado (integrado com Cálculo I)", f"C9 falhou: {tde_c9['descricao']}"

    # Validação de data de TDE fora do bloco ou do semestre: mantém e gera aviso
    ras_fora = [{
        "nome": "RA1",
        "percentual": 50,
        "temas": ["A"],
        "tde": [{"horas": 2, "descricao": "TDE Fora", "data": "2026-12-01"}]
    }, {
        "nome": "RA2",
        "percentual": 50,
        "temas": ["B"],
        "tde": []
    }]
    linhas_fora, avisos_fora = gera_cronograma(
        data_inicio=date(2026, 8, 4),
        data_fim=date(2026, 8, 25),
        dias_semana={"terca": 4},
        feriados_nacionais=set(),
        recessos_manuais=[],
        ras=ras_fora,
    )
    assert any("fora do intervalo do semestre" in a and "2026-12-01" in a for a in avisos_fora), f"aviso de semestre ausente: {avisos_fora}"
    assert any(l.get("data_iso") == "2026-12-01" for l in linhas_fora), "linha de TDE fora do intervalo deveria ser mantida"

    print(f"demo ok — {len(linhas)} linhas geradas, {len(avisos)} avisos: {avisos} | feriado-linha: {len(linhas_fer)} | semana: {len(linhas_semana)} | 2ª chamada: {len(linhas_2a)} | tema sobrando: {avisos_sobra}")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
