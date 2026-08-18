# -*- coding: utf-8 -*-
"""Verificações determinísticas (sem IA) sobre o conteúdo do documento.

Não altera nada: apenas devolve avisos para a usuária conferir.
A principal é a consistência de datas — o tipo de erro que passa
despercebido na leitura e compromete um relatório oficial.
"""
from __future__ import annotations

import datetime
import re
import statistics

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_EXT = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-zçã]+)\s+de\s+(\d{4})\b", re.I)


def _mk(d: int, m: int, y: int):
    if y < 100:
        y += 2000 if y < 70 else 1900
    try:
        return datetime.date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[tuple[datetime.date, str]]:
    """Datas encontradas no texto, como (data, trecho literal)."""
    out = []
    for m in _NUM.finditer(text):
        d = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            out.append((d, m.group(0)))
    for m in _EXT.finditer(text):
        mes = MESES.get(m.group(2).lower())
        if mes:
            d = _mk(int(m.group(1)), mes, int(m.group(3)))
            if d:
                out.append((d, m.group(0)))
    return out


def check_dates(paragraphs: list[str],
                doc_date: datetime.date | None = None) -> list[str]:
    """Avisos sobre datas suspeitas.

    Detecta três situações:
      1. data posterior à data do documento (evento no futuro);
      2. ano fora de faixa plausível;
      3. ano destoante da vizinhança cronológica (ex.: um 2026 no meio
         de uma sequência de 2021) — o erro de digitação clássico.
    """
    avisos: list[str] = []

    seq: list[tuple[datetime.date, str, int]] = []
    for i, p in enumerate(paragraphs):
        for d, txt in find_dates(p):
            seq.append((d, txt, i))
    if not seq:
        return avisos
    if doc_date is None:
        doc_date = seq[0][0]

    # 1) datas no futuro — ignoradas quando o parágrafo indica agendamento
    agenda = re.compile(
        r"agendad|marcad|previst|pr[oó]xim|programad|remarcad", re.I)
    for d, txt, i in seq:
        if d > doc_date + datetime.timedelta(days=1):
            if not agenda.search(paragraphs[i]):
                avisos.append(
                    f"Data “{txt}” é posterior à data do documento "
                    f"({doc_date.strftime('%d/%m/%Y')}) — confira se está "
                    f"correta (ou se falta indicar que é um agendamento).")
        elif not (1950 <= d.year <= doc_date.year + 1):
            avisos.append(f"Data “{txt}” tem ano fora do esperado — confira.")

    # 2) ano isolado, muito distante da vizinhança cronológica
    corpo = seq[1:]                      # ignora a data do cabeçalho
    anos = [s[0].year for s in corpo]
    if len(corpo) >= 5:
        for k, (d, txt, i) in enumerate(corpo):
            viz = anos[max(0, k - 3):k] + anos[k + 1:k + 4]
            if len(viz) < 4 or max(viz) - min(viz) > 2:
                continue   # vizinhança incoerente (ex.: datas de nascimento)
            if d.year > max(viz) + 1 or d.year < min(viz) - 1:
                msg = (f"Data “{txt}” destoa das datas ao redor "
                       f"({min(viz)}–{max(viz)}) — possível erro de digitação.")
                if msg not in avisos:
                    avisos.append(msg)

    return avisos


def check_canonical(paragraphs: list[str], blocos: dict[str, str],
                    limiar: float = 0.80) -> list[str]:
    """Compara parágrafos com os blocos institucionais canônicos salvos.

    Avisa quando um parágrafo é claramente uma variação do bloco oficial
    (mesma abertura, texto parecido) mas não idêntico.
    """
    import difflib
    avisos = []
    for nome, canon in (blocos or {}).items():
        canon_n = re.sub(r"\s+", " ", canon).strip()
        if not canon_n:
            continue
        melhor, score = None, 0.0
        for p in paragraphs:
            pn = re.sub(r"\s+", " ", p).strip()
            s = difflib.SequenceMatcher(None, pn[:400], canon_n[:400]).ratio()
            if s > score:
                melhor, score = pn, s
        if melhor and limiar <= score < 0.995:
            avisos.append(
                f"O trecho institucional “{nome}” aparece com pequenas "
                f"diferenças em relação ao texto oficial salvo "
                f"({score * 100:.0f}% de semelhança).")
    return avisos
