# -*- coding: utf-8 -*-
"""Arquivo pesquisável dos documentos — busca por conteúdo.

Cada documento processado entra num índice local (SQLite). Também é
possível indexar pastas antigas de uma vez. A busca é por palavra:
"convulsão", "rifa", "medida protetiva", "CAPS"…

O índice fica só no computador da usuária, na pasta de configuração.
"""
from __future__ import annotations

import datetime
import glob
import os
import re
import sqlite3
import zipfile

import settings

BANCO = "arquivo.db"


class _Conn(sqlite3.Connection):
    """Conexão que aceita marcar se o índice de texto completo existe."""
    fts = False


def _conn() -> _Conn:
    c = sqlite3.connect(os.path.join(settings._config_dir(), BANCO),
                        factory=_Conn)
    c.execute("""CREATE TABLE IF NOT EXISTS docs(
        caminho TEXT PRIMARY KEY, nome TEXT, perfil TEXT,
        data_doc TEXT, indexado TEXT, texto TEXT)""")
    try:
        c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS busca
                     USING fts5(caminho UNINDEXED, nome, texto,
                                tokenize='unicode61 remove_diacritics 2')""")
        c.execute("SELECT 1 FROM busca LIMIT 1")
        c.fts = True
    except sqlite3.Error:
        c.fts = False
    return c


def texto_do_docx(path: str) -> str:
    """Texto simples de um .docx, sem depender do motor de formatação."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    xml = re.sub(r"<w:del\b.*?</w:del>", "", xml, flags=re.S)
    partes = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", xml, flags=re.S)
    txt = " ".join(partes)
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&apos;", "'")):
        txt = txt.replace(ent, ch)
    return re.sub(r"\s+", " ", txt).strip()


def indexar(path: str, perfil: str = "", data_doc: str = "",
            texto: str | None = None) -> bool:
    if texto is None:
        texto = texto_do_docx(path)
    if not texto:
        return False
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    nome = os.path.basename(path)
    c = _conn()
    with c:
        c.execute("INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?)",
                  (path, nome, perfil, data_doc, agora, texto))
        if c.fts:
            c.execute("DELETE FROM busca WHERE caminho=?", (path,))
            c.execute("INSERT INTO busca VALUES (?,?,?)", (path, nome, texto))
    c.close()
    return True


def indexar_pasta(pasta: str, progresso=lambda m: None) -> int:
    """Indexa todos os .docx de uma pasta (e subpastas). Devolve o total."""
    arquivos = [a for a in glob.glob(os.path.join(pasta, "**", "*.docx"),
                                     recursive=True)
                if not os.path.basename(a).startswith("~$")]
    n = 0
    for i, a in enumerate(arquivos, 1):
        progresso(f"Indexando {i}/{len(arquivos)}…")
        if indexar(a):
            n += 1
    return n


# sufixos removidos para casar flexões ("convulsão" acha "convulsivos")
_SUFIXOS = ("ções", "ção", "ões", "ão", "mente", "idade", "ivos", "ivas",
            "ivo", "iva", "ados", "adas", "ado", "ada", "ndo", "es", "os",
            "as")


def _radical(tok: str) -> str:
    if len(tok) >= 6:
        for suf in _SUFIXOS:
            if tok.lower().endswith(suf) and len(tok) - len(suf) >= 4:
                return tok[:len(tok) - len(suf)]
    return tok


def buscar(termo: str, limite: int = 40) -> list[dict]:
    termo = termo.strip()
    if not termo:
        return []
    c = _conn()
    linhas = []
    try:
        if c.fts:
            # busca por prefixo: pega flexões ("convuls" → convulsão,
            # convulsivo) e erros de digitação no final da palavra
            toks = [re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", t) for t in termo.split()]
            toks = [_radical(t) for t in toks if len(t) >= 2]
            if not toks:
                raise sqlite3.Error
            consulta = " ".join(f'"{t}"*' for t in toks)
            linhas = c.execute(
                "SELECT b.caminho, b.nome, snippet(busca, 2, '«', '»', '…', 12)"
                " FROM busca b WHERE busca MATCH ? LIMIT ?",
                (consulta, limite)).fetchall()
        else:
            raise sqlite3.Error
    except sqlite3.Error:
        like = f"%{termo}%"
        linhas = [(r[0], r[1], (r[2] or "")[:160] + "…") for r in c.execute(
            "SELECT caminho, nome, texto FROM docs WHERE texto LIKE ? LIMIT ?",
            (like, limite)).fetchall()]
    c.close()
    return [{"caminho": l[0], "nome": l[1], "trecho": l[2]} for l in linhas]


def total() -> int:
    c = _conn()
    n = c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    c.close()
    return n
