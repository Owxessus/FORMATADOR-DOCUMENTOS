# -*- coding: utf-8 -*-
"""Atualização automática a partir das Releases do GitHub.

O app consulta a última versão publicada, avisa quando há novidade e,
com um clique, baixa e se substitui sozinho. Funciona sem senha desde
que o repositório seja público; sendo privado, apenas avisa que há
versão nova e abre a página de download.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request

import version

API = f"https://api.github.com/repos/{version.REPO}/releases/latest"
PAGINA = f"https://github.com/{version.REPO}/releases/latest"


def _tupla(v: str) -> tuple:
    v = v.strip().lstrip("vV")
    partes = []
    for p in v.split("."):
        num = "".join(c for c in p if c.isdigit())
        partes.append(int(num) if num else 0)
    return tuple(partes + [0] * (3 - len(partes)))[:3]


def checar() -> dict | None:
    """Devolve {'versao', 'url', 'notas'} se houver versão mais nova."""
    try:
        req = urllib.request.Request(
            API, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "Formatador"})
        with urllib.request.urlopen(req, timeout=15) as r:
            import json
            data = json.load(r)
    except Exception:  # noqa: BLE001 — sem internet/privado: silencioso
        return None
    tag = data.get("tag_name", "")
    if not tag or _tupla(tag) <= _tupla(version.VERSION):
        return None
    url = ""
    for a in data.get("assets", []):
        if a.get("name", "").lower().endswith(".exe"):
            url = a.get("browser_download_url", "")
    return {"versao": tag.lstrip("vV"), "url": url,
            "notas": (data.get("body") or "").strip()[:400]}


def baixar_e_instalar(url: str, progresso=lambda m: None) -> None:
    """Baixa o novo executável e agenda a troca + reinício.

    O próprio programa não pode se sobrescrever enquanto roda, então um
    script auxiliar espera o fechamento, troca o arquivo e reabre.
    """
    if not url or not getattr(sys, "frozen", False):
        raise RuntimeError("Atualização automática só funciona no aplicativo "
                           "instalado (.exe).")
    destino = sys.executable
    progresso("Baixando a nova versão…")
    tmp = os.path.join(tempfile.gettempdir(), "Formatador_novo.exe")
    req = urllib.request.Request(url, headers={"User-Agent": "Formatador"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        f.write(r.read())

    progresso("Instalando…")
    bat = os.path.join(tempfile.gettempdir(), "atualizar_formatador.bat")
    with open(bat, "w", encoding="cp1252", errors="ignore") as f:
        f.write(
            "@echo off\r\n"
            "timeout /t 3 /nobreak >nul\r\n"
            f'move /Y "{tmp}" "{destino}" >nul\r\n'
            f'start "" "{destino}"\r\n'
            'del "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    sys.exit(0)
