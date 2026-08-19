# -*- coding: utf-8 -*-
"""Onde salvar os arquivos gerados.

Três modos (Configurações): mesma pasta do original, uma pasta fixa, ou
perguntar a cada arquivo. Além disso, a usuária pode pedir a pasta em
português no campo de instruções — "salvar na área de trabalho" — sem
precisar mexer em configuração.
"""
from __future__ import annotations

import os
import re

# pastas conhecidas → caminho no Windows (com equivalentes em Linux/Mac)
def _home(*partes) -> str:
    return os.path.join(os.path.expanduser("~"), *partes)


def _desktop() -> str:
    for nome in ("Desktop", "Área de Trabalho", "Area de Trabalho"):
        p = _home(nome)
        if os.path.isdir(p):
            return p
    return _home("Desktop")


def _documentos() -> str:
    for nome in ("Documents", "Documentos"):
        p = _home(nome)
        if os.path.isdir(p):
            return p
    return _home("Documents")


CONHECIDAS = [
    (r"[áa]rea de trabalho|desktop", _desktop),
    (r"meus documentos|documentos|documents", _documentos),
    (r"downloads|transfer[êe]ncias", lambda: _home("Downloads")),
]

# "salve/salvar/gravar ... na/em/para <destino>"
_PEDIDO = re.compile(
    r"(?:salv(?:e|ar)|grav(?:e|ar)|colocar?|jog(?:ue|ar))\s+"
    r"(?:o[s]?\s+arquivos?\s+|tudo\s+|isso\s+)?"
    r"(?:n[ao]s?|em|para|no)\s+(.{2,120}?)"
    r"(?=\s+(?:e|mas|por[ée]m|tamb[ée]m|al[ée]m)\s|[.;,\n]|$)", re.I)

_MESMA = re.compile(r"mesma pasta|pasta do arquivo|pasta de origem", re.I)


def interpretar(instrucoes: str) -> tuple[str | None, str]:
    """Lê um pedido de pasta nas instruções.

    Devolve (pasta_ou_None, instrucoes_sem_o_pedido). Quando devolve
    a string vazia como pasta, significa “mesma pasta do arquivo”.
    """
    if not instrucoes:
        return None, instrucoes

    m = _PEDIDO.search(instrucoes)
    if not m:
        return None, instrucoes
    alvo = m.group(1).strip()
    limpo = (instrucoes[:m.start()] + " " + instrucoes[m.end():]).strip()
    limpo = re.sub(r"\s{2,}", " ", limpo).strip(" ,;.")
    limpo = re.sub(r"^(?:e|mas|por[ée]m|tamb[ée]m|al[ée]m disso)\s+", "",
                   limpo, flags=re.I).strip(" ,;.")

    if _MESMA.search(alvo):
        return "", limpo

    # caminho explícito (C:\... ou /...)
    caminho = re.search(r"[A-Za-z]:\\[^\s,;]*|/[^\s,;]+", alvo)
    if caminho:
        p = caminho.group(0).strip().strip('"')
        return (p, limpo) if os.path.isdir(p) else (None, instrucoes)

    for padrao, fn in CONHECIDAS:
        if re.search(padrao, alvo, re.I):
            destino = fn()
            os.makedirs(destino, exist_ok=True)
            return destino, limpo

    # subpasta conhecida: "na pasta Relatórios dos Documentos"
    nome = re.sub(r"^pasta\s+", "", alvo, flags=re.I).strip().strip('"')
    if nome and len(nome) <= 60:
        for base in (_documentos(), _desktop(), os.path.expanduser("~")):
            p = os.path.join(base, nome)
            if os.path.isdir(p):
                return p, limpo
    return None, instrucoes


def resolver(cfg: dict, origem: str, perguntar_fn=None,
             instrucoes: str = "") -> tuple[str | None, str]:
    """Decide a pasta de saída. Devolve (pasta_ou_None, instrucoes_limpas)."""
    pedida, limpas = interpretar(instrucoes)
    if pedida is not None:
        return (pedida or None), limpas

    modo = cfg.get("out_mode", "mesma")
    if modo == "fixa" and cfg.get("out_dir"):
        return cfg["out_dir"], limpas
    if modo == "perguntar" and perguntar_fn:
        escolhida = perguntar_fn()
        return (escolhida or None), limpas
    return None, limpas
