# -*- coding: utf-8 -*-
"""Teste do motor docx com documentos locais (não incluídos no repositório).

Uso:
    FIXTURES_DIR=/caminho/dos/docx python tests/test_engine.py

Para cada NOME.docx em FIXTURES_DIR, se existir NOME_gabarito.py (com UNITS =
[(kind, original, corrigido), ...]) o corretor simulado usa essas correções;
sem gabarito, roda com corretor identidade (só formata) — a autoverificação
continua valendo nos dois casos.
"""
import difflib
import glob
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import docx_engine as eng  # noqa: E402

FIXTURES = os.environ.get("FIXTURES_DIR",
                          os.path.join(os.path.dirname(__file__), "fixtures"))
OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)


def norm(t):
    return re.sub(r"\s+", " ", t).strip()


def make_mock(units):
    pairs = [(norm(o), c) for _, o, c in units]

    def corrector(texts, kinds, extra):
        out = []
        for t in texts:
            nt = norm(t).lstrip("•").strip()
            best, score = None, 0.0
            for o, c in pairs:
                s = difflib.SequenceMatcher(None, nt, o).ratio()
                if s > score:
                    best, score = c, s
            out.append(best if score > 0.75 else t)
        return out
    return corrector


def load_units(py_path):
    spec = importlib.util.spec_from_file_location("gabarito", py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.UNITS


docs = sorted(glob.glob(os.path.join(FIXTURES, "*.docx")))
if not docs:
    print(f"Nenhum .docx em {FIXTURES} — defina FIXTURES_DIR.")
    sys.exit(0)

ok_all = True
for path in docs:
    name = os.path.splitext(os.path.basename(path))[0]
    gab = os.path.join(FIXTURES, f"{name}_gabarito.py")
    corrector = make_mock(load_units(gab)) if os.path.exists(gab) \
        else (lambda ts, ks, e: list(ts))
    res = eng.process(path, corrector, out_dir=OUT, progress=lambda m: None)
    ok_all &= res["verified"]
    print(f"[{'OK ' if res['verified'] else 'FAIL'}] {name}: "
          f"{res['paragraphs']} parágrafos, {res['changed']} alterados, "
          f"avisos={len(res['warnings'])}")
    for w in res["warnings"]:
        print("        aviso:", w[:100])

print("\nRESULTADO GERAL:", "PASSOU" if ok_all else "FALHOU")
sys.exit(0 if ok_all else 1)
