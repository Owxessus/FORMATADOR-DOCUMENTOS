# -*- coding: utf-8 -*-
"""Comandos que a usuária pode escrever no campo de instruções.

O campo serve para pedidos pontuais sobre o texto, mas também aceita
alguns comandos que o app executa sozinho e remove antes de enviar o
resto para a IA:

    lembrar: a assistente social do serviço é a Gilmara
    proteger: Thayllе, Nhocuné, Vila Reencontro
    salvar na área de trabalho          (tratado em outdir.py)
"""
from __future__ import annotations

import re

import memory

_LEMBRAR = re.compile(
    r"(?:lembr(?:ar|e|a)|anot(?:ar|e)|memoriz(?:ar|e)|guard(?:ar|e))"
    r"\s*(?:que\s+|isso[:,]?\s*)?[:\-]?\s*(.+?)(?=[.;\n]|$)", re.I)
_PROTEGER = re.compile(
    r"(?:proteger|n[ãa]o corrig(?:ir|a)|preserv(?:ar|e))"
    r"\s*(?:os? termos?|as? palavras?|os? nomes?)?\s*[:\-]?\s*(.+?)"
    r"(?=[.;\n]|$)", re.I)


def processar(instrucoes: str, cfg: dict) -> tuple[str, list[str]]:
    """Executa os comandos encontrados. Devolve (instruções_limpas, avisos)."""
    avisos: list[str] = []
    if not instrucoes:
        return instrucoes, avisos
    texto = instrucoes

    for m in list(_LEMBRAR.finditer(texto)):
        fato = m.group(1).strip(" ,;.")
        if len(fato) >= 4:
            memory.adicionar_fato(fato)
            avisos.append(f"Guardado na memória: “{fato[:70]}”")
            texto = texto.replace(m.group(0), " ")

    for m in list(_PROTEGER.finditer(texto)):
        bruto = m.group(1).strip(" ,;.")
        termos = [t.strip() for t in re.split(r"[,;]| e ", bruto) if t.strip()]
        termos = [t for t in termos if 1 < len(t) <= 40]
        if termos:
            lista = list(cfg.get("protected_terms") or [])
            novos = [t for t in termos if t not in lista]
            if novos:
                cfg["protected_terms"] = lista + novos
                import settings
                settings.save(cfg)
                avisos.append("Termos protegidos: " + ", ".join(novos))
            texto = texto.replace(m.group(0), " ")

    texto = re.sub(r"\s{2,}", " ", texto).strip(" ,;.")
    return texto, avisos
