#!/usr/bin/env python3
"""Cruza o calendário institucional (extraído de um PDF de resolução, tipo
CONSUN) com o `cronograma.json` já calculado por `gerar_cronograma.py`, e
aponta desalinhamentos — não corrige nada sozinho, só avisa.

Só biblioteca padrão do Python — sem pip install, sem rede.

Uso:
    python3 verifica_calendario_institucional.py cronograma.json calendario_institucional.json

calendario_institucional.json é uma lista de eventos extraídos manualmente do
PDF institucional (o script não lê PDF — quem chama já converteu via
markitdown e leu o texto). Cada item:
{
  "data": "2026-02-16",             # obrigatório, YYYY-MM-DD
  "data_fim": "2026-02-17",         # opcional — range de datas (default: só "data")
  "tipo": "recesso",                # "recesso" | "evento" | "limite_inicio" | "limite_fim"
  "descricao": "Carnaval"
}

Tipos:
- "recesso": dia sem aula por decisão institucional (não é feriado nacional
  — esses já vêm da BrasilAPI dentro de gerar_cronograma.py). Se o
  cronograma ainda tem aula marcada (RA != "-") numa data de recesso, avisa
  — normalmente indica que a data faltou em `recessos_manuais`.
- "evento": ocupa o dia mas não necessariamente cancela aula (Semana
  Acadêmica, SEMIC/SEMITI, Formação Docente) — avisa se coincide com aula
  normal marcada, pra o professor decidir se vira linha manual (RA "-") ou
  se mantém.
- "limite_inicio"/"limite_fim": data oficial de início/fim das aulas do
  semestre — avisa se o cronograma calculado começa antes ou termina depois
  desse limite.
"""
import json
import sys
from datetime import date, timedelta


def _datas_no_range(evento):
    inicio = date.fromisoformat(evento["data"])
    fim = date.fromisoformat(evento.get("data_fim") or evento["data"])
    d = inicio
    while d <= fim:
        yield d
        d += timedelta(days=1)


def _range_cronograma(linhas):
    """Menor/maior data_iso entre as linhas com data fixa (ignora TDE/linhas
    avulsas sem data). None, None se não houver nenhuma."""
    datas = [l["data_iso"] for l in linhas if l.get("data_iso")]
    if not datas:
        return None, None
    return date.fromisoformat(min(datas)), date.fromisoformat(max(datas))


def verifica_calendario(linhas, eventos):
    """Retorna lista de avisos (str). `linhas` é o `cronograma` de
    cronograma.json, `eventos` é a lista de calendario_institucional.json."""
    avisos = []
    por_data = {l["data_iso"]: l for l in linhas if l.get("data_iso")}
    inicio_cron, fim_cron = _range_cronograma(linhas)

    for evento in eventos:
        tipo = evento["tipo"]
        desc = evento.get("descricao", "")

        if tipo == "recesso":
            for d in _datas_no_range(evento):
                linha = por_data.get(d.isoformat())
                if linha and linha["ra"] != "-":
                    avisos.append(
                        f"recesso institucional não excluído: {desc} ({d.isoformat()}) "
                        f"ainda aparece como aula (RA {linha['ra']}) no cronograma — "
                        f"confira 'recessos_manuais' em dados_cronograma.json"
                    )

        elif tipo == "evento":
            for d in _datas_no_range(evento):
                linha = por_data.get(d.isoformat())
                if linha and linha["ra"] != "-":
                    avisos.append(
                        f"evento institucional coincide com aula: {desc} ({d.isoformat()}) "
                        f"tem aula normal marcada (RA {linha['ra']}) — considere linha manual "
                        f"(RA \"-\") ou ajustar a data"
                    )

        elif tipo == "limite_inicio":
            limite = date.fromisoformat(evento["data"])
            if inicio_cron and inicio_cron < limite:
                avisos.append(
                    f"cronograma começa antes do início oficial das aulas: "
                    f"{inicio_cron.isoformat()} < {limite.isoformat()} ({desc})"
                )

        elif tipo == "limite_fim":
            limite = date.fromisoformat(evento["data"])
            if fim_cron and fim_cron > limite:
                avisos.append(
                    f"cronograma termina depois do encerramento oficial das aulas: "
                    f"{fim_cron.isoformat()} > {limite.isoformat()} ({desc})"
                )

        else:
            avisos.append(f"tipo de evento desconhecido, ignorado: {tipo!r} ({desc})")

    return avisos


def main():
    if len(sys.argv) != 3:
        print("uso: python3 verifica_calendario_institucional.py cronograma.json calendario_institucional.json", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        linhas = json.load(f)["cronograma"]
    with open(sys.argv[2], encoding="utf-8") as f:
        eventos = json.load(f)

    avisos = verifica_calendario(linhas, eventos)
    print(json.dumps({"avisos": avisos}, ensure_ascii=False, indent=2))


def demo():
    """python3 verifica_calendario_institucional.py --demo"""
    linhas = [
        {"data_iso": "2026-02-16", "ra": "RA1", "descricao": "Introdução"},  # cai num recesso, não excluído
        {"data_iso": "2026-02-23", "ra": "RA1", "descricao": "Fundamentos"},  # cai num evento (Semana Acadêmica)
        {"data_iso": "2026-03-02", "ra": "RA1", "descricao": "Prática"},
        {"data_iso": "2026-06-27", "ra": "RA2", "descricao": "Revisão"},
        {"data_iso": None, "ra": "RA1", "descricao": "TDE"},  # sem data, ignorada no range
    ]
    eventos = [
        {"data": "2026-02-16", "data_fim": "2026-02-17", "tipo": "recesso", "descricao": "Carnaval"},
        {"data": "2026-02-23", "data_fim": "2026-02-28", "tipo": "evento", "descricao": "Semana de Integração Acadêmica"},
        {"data": "2026-03-05", "tipo": "limite_inicio", "descricao": "Início oficial das aulas"},  # cronograma começa antes (02/03) -> aviso
        {"data": "2026-06-20", "tipo": "limite_fim", "descricao": "Encerramento oficial das aulas"},  # cronograma termina depois (27/06) -> aviso
        {"data": "2026-04-02", "tipo": "recesso", "descricao": "Quinta-feira Santa"},  # sem aula nessa data -> sem aviso
    ]

    avisos = verifica_calendario(linhas, eventos)
    assert len(avisos) == 4, f"esperava 4 avisos, veio {len(avisos)}: {avisos}"
    assert any("Carnaval" in a and "não excluído" in a for a in avisos), "aviso de recesso não gerado"
    assert any("Semana de Integração Acadêmica" in a and "coincide" in a for a in avisos), "aviso de evento não gerado"
    assert any("antes do início oficial" in a for a in avisos), "aviso de limite_inicio não gerado"
    assert any("depois do encerramento oficial" in a for a in avisos), "aviso de limite_fim não gerado"
    assert not any("Quinta-feira Santa" in a for a in avisos), "recesso sem aula marcada não deveria gerar aviso"

    print(f"demo ok — {len(avisos)} avisos gerados, checagens batem")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
