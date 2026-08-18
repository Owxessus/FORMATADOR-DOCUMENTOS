# -*- coding: utf-8 -*-
"""Preferências locais do app (salvas na pasta do usuário)."""
from __future__ import annotations

import json
import os
import sys

APP_NAME = "FormatadorRelatorios"

DEFAULTS = {
    "api_key": "",
    "model": "google/gemini-3.7-flash",
    "always_on_top": True,
    "generate_pdf": "perguntar",   # sempre | nunca | perguntar
    "out_dir": "",                 # vazio = mesma pasta do arquivo
    "onboarded": False,
    "history": [],                 # [{file, when, cost, changed}]
    "theme": "light",              # light | dark
    # termos que a IA nunca deve "corrigir" (siglas, nomes, medicações)
    "protected_terms": [
        "CAE", "CREAS", "CRAS", "CAPS", "SAMU", "UPA", "UBS", "AMA", "AME",
        "GCM", "INSS", "AVCB", "EPIs", "OSC", "APOIO", "CID", "CRM", "CREMESP",
        "CRP", "CRESS", "SUAS", "PAEFI", "LGBTQIAPN+", "Penha",
    ],
}


def _config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(_config_path(), encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def save(cfg: dict) -> None:
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def add_history(cfg: dict, entry: dict, keep: int = 50) -> None:
    cfg["history"] = ([entry] + cfg.get("history", []))[:keep]
    save(cfg)
