# -*- coding: utf-8 -*-
"""Memória base institucional — persiste entre atualizações do app.

Guarda o que é estável no serviço e não deveria ser redigitado a cada
relatório: blocos de texto oficiais (a descrição do CAE, por exemplo) e
os perfis de documento (quem assina, que instruções valem para cada tipo).

Fica em memoria.json, separado das preferências, para poder ser copiado
ou compartilhado com outra unidade.
"""
from __future__ import annotations

import json
import os

import settings

ARQ = "memoria.json"

PERFIS_PADRAO = {
    "Detectar automaticamente": {
        "assinatura": [], "instrucoes": "", "blocos": [], "titulos": []},
    "Relatório Técnico": {
        "assinatura": ["Equipe Técnica"],
        "instrucoes": "",
        "blocos": ["Descrição do serviço"],
        "titulos": ["relatório técnico"]},
    "Relatório de Ocorrência": {
        "assinatura": ["Equipe Técnica"],
        "instrucoes": "",
        "blocos": [],
        "titulos": ["ocorrência", "ocorrencia"]},
    "Relatório de Gerência / resposta a órgão": {
        # ajuste em Memória → Perfis para o nome da sua unidade
        "assinatura": ["Gerente"],
        "instrucoes": "",
        "blocos": ["Descrição do serviço", "Estrutura física",
                   "Quadro de funcionários"],
        "titulos": ["relatório"]},
}

DEFAULTS = {"blocos": {}, "perfis": PERFIS_PADRAO, "fatos": []}


def _path() -> str:
    return os.path.join(settings._config_dir(), ARQ)


def load() -> dict:
    d = {"blocos": dict(DEFAULTS["blocos"]),
         "perfis": {k: dict(v) for k, v in PERFIS_PADRAO.items()},
         "fatos": []}
    try:
        with open(_path(), encoding="utf-8") as f:
            saved = json.load(f)
        d["blocos"].update(saved.get("blocos", {}))
        d["fatos"] = list(saved.get("fatos", []))
        for nome, perfil in (saved.get("perfis") or {}).items():
            base = dict(PERFIS_PADRAO.get(nome, {
                "assinatura": [], "instrucoes": "", "blocos": [],
                "titulos": []}))
            base.update(perfil)
            d["perfis"][nome] = base
    except (OSError, json.JSONDecodeError):
        pass
    return d


def save(mem: dict) -> None:
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


def detectar_perfil(paragraphs: list[str], mem: dict) -> str:
    """Escolhe o perfil pelo título do documento (primeiros parágrafos)."""
    cabeca = " ".join(paragraphs[:14]).lower()
    melhor, tamanho = "Detectar automaticamente", 0
    for nome, p in mem.get("perfis", {}).items():
        for t in p.get("titulos", []):
            if t and t in cabeca and len(t) > tamanho:
                melhor, tamanho = nome, len(t)
    return melhor


def adicionar_fato(texto: str) -> None:
    """Guarda um fato institucional na memória (usado como contexto)."""
    mem = load()
    texto = texto.strip()
    if texto and texto not in mem["fatos"]:
        mem["fatos"].append(texto)
        save(mem)
