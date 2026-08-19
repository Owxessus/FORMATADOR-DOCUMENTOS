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
    """Baixa a nova versão e agenda a troca do executável.

    Cuidados aprendidos na prática:
      * o programa PRECISA sair de verdade antes da troca — o Windows não
        deixa sobrescrever um .exe em uso. Como esta função roda numa
        thread, sys.exit() não serve: encerra só a thread. Usamos os._exit;
      * o script espera o PID sumir (não um tempo fixo) e tenta a troca
        várias vezes, para o caso de o antivírus segurar o arquivo;
      * se a troca falhar, o script abre a versão antiga e deixa o novo
        executável na Área de Trabalho, com aviso.
    """
    if not url or not getattr(sys, "frozen", False):
        raise RuntimeError("A atualização automática só funciona no "
                           "aplicativo instalado (.exe).")
    destino = os.path.abspath(sys.executable)
    progresso("Baixando a nova versão…")
    tmp = os.path.join(tempfile.gettempdir(), "Formatador_novo.exe")
    req = urllib.request.Request(url, headers={"User-Agent": "Formatador"})
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
        f.write(r.read())

    # confere que baixou um executável de verdade antes de trocar
    with open(tmp, "rb") as f:
        if f.read(2) != b"MZ" or os.path.getsize(tmp) < 5_000_000:
            os.remove(tmp)
            raise RuntimeError("O download veio incompleto. Tente de novo.")

    progresso("Instalando… o programa vai reabrir sozinho.")
    pid = os.getpid()
    reserva = os.path.join(os.path.expanduser("~"), "Desktop",
                           "Formatador_NOVO.exe")
    bat = os.path.join(tempfile.gettempdir(), "atualizar_formatador.bat")
    with open(bat, "w", encoding="cp1252", errors="ignore") as f:
        f.write(f"""@echo off
rem espera o programa fechar de verdade (no maximo ~30s)
set /a tentativas=0
:esperar
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul || goto trocar
set /a tentativas+=1
if %tentativas% GEQ 30 goto trocar
timeout /t 1 /nobreak >nul
goto esperar

:trocar
set /a n=0
:tentar
move /Y "{tmp}" "{destino}" >nul 2>&1
if not errorlevel 1 goto pronto
set /a n+=1
if %n% GEQ 8 goto falhou
timeout /t 2 /nobreak >nul
goto tentar

:falhou
copy /Y "{tmp}" "{reserva}" >nul 2>&1
start "" "{destino}"
msg %USERNAME% "Nao foi possivel substituir o programa automaticamente. O novo executavel foi salvo na Area de Trabalho como Formatador_NOVO.exe - basta substituir manualmente." 2>nul
del "%~f0"
exit

:pronto
start "" "{destino}"
del "%~f0"
""")
    subprocess.Popen(["cmd", "/c", bat],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    # encerra o processo INTEIRO (sys.exit sairia só desta thread)
    os._exit(0)
